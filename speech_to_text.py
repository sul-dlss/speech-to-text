#!/usr/bin/env python3

import argparse
import datetime
import json
import logging
import os
import sys
import uuid
from functools import cache
from pathlib import Path

import boto3
import dotenv
import torch
import whisper
from whisper.utils import get_writer

dotenv.load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s :: %(levelname)s :: %(message)s", 
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)

def main(daemon=True):
    # loop forever looking for jobs unless daemon says not to
    while True:
        job = get_job()

        try:
            if job is None:
                logging.info("no jobs waiting in the todo queue")
            else:
                logging.info(f"starting job {job['id']}")
                download_media(job)
                run_whisper(job)
                upload_results(job)
                finish_job(job)
                logging.info(f"finished job {job['id']}")
        except KeyboardInterrupt:
            logging.info("exiting")
            sys.exit()
        except Exception as e:
            logging.error(f"error while processing job {job['id']}: {e}")
            report_error(job, e)

        if not daemon:
            break


def get_job():
    """
    Fetch the next job that is queued for processing. If no job is found in WaitTimeSeconds
    seconds None will be returned.
    """
    queue = get_todo_queue()
    logging.info("looking for messages in the todo queue")
    jobs = queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=10)

    if len(jobs) == 1:
        msg = jobs[0]
        job = json.loads(msg.body)

        # The default Visibilty Timeout for a queue is 30 seconds. If we don't delete the
        # message or update its Visibility Timeout in that time SQS will automatically
        # requeue the message. This could lead to multiple workers working on
        # the same job!
        #
        # While we could set the Visibility Timeout to some higher value (less than the 12 hour
        # maximum), the approach taken here is to delete the message once it has been received.
        # This means if processing fails for whatever reason we won't get the job automatically
        # requeued. But this is a good thing since Whisper processing on a GPU is expensive.
        # Instead exceptions will be caught and an error message will be sent to the Done queue.
        #
        # See: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
        msg.delete()

        return job
    elif len(jobs) == 0:
        return None
    else:
        # this should never happen
        raise Exception(f"expected 1 job from queue but got {len(jobs)}")


def download_media(job):
    bucket = get_bucket()
    output_dir = get_output_dir(job)
    for media_file in job["media"]:
        key = f"media/{job['id']}/{media_file}"
        bucket.download_file(key, output_dir / media_file)


def run_whisper(job):
    # this code and writer_options() below is adapted from
    # https://github.com/openai/whisper/blob/main/whisper/transcribe.py
    options = job.get("options", {}).copy()

    model_name = options.get("model", "small")
    model = load_whisper_model(model_name)

    output_dir = get_output_dir(job)

    writer = get_writer(output_format="all", output_dir=output_dir)
    writer_options = get_writer_options(options)

    for media_file in job["media"]:
        audio_file = str(output_dir / media_file)
        logging.info(f"running whisper on {audio_file} with options {options}")

        # remove model name from options to not interfere with model instance below
        options.pop("model", None)

        result = whisper.transcribe(audio=audio_file, model=model, **options)
        logging.info(f"whisper result: {result}")

        logging.info(f"writing output using writer_options: {writer_options}")
        writer(result, media_file, writer_options)

    job["finished"] = now()
    tech_md_dict = {
        "speech_to_text_extraction_program": {
            "name": "whisper",
            "version": whisper.version.__version__,
        },
        "effective_options": options,
        "effective_writer_options": writer_options,
        "effective_model_name": model_name,
    }
    job["extraction_technical_metadata"] = tech_md_dict

    return job


def upload_results(job):
    """
    Upload the Whisper output to S3, and put the job file there too.
    """
    bucket = get_bucket()

    bucket.put_object(Key=f"out/{job['id']}.json", Body=json.dumps(job, indent=2))

    output_dir = get_output_dir(job)
    for path in output_dir.iterdir():
        # don't upload the media again
        if path.name in job["media"]:
            continue

        key = f"out/{job['id']}/{path.name}"
        logging.info(f"wrote whisper result to s3://{bucket.name}/{key}")
        bucket.upload_file(path, key)


def finish_job(job):
    queue = get_done_queue()
    logging.info(f"sending message to done queue: {job}")
    queue.send_message(MessageBody=json.dumps(job))

    # clean up media on s3
    bucket = get_bucket()
    for media_file in job["media"]:
        obj = bucket.Object(f"media/{job['id']}/{media_file}")
        logging.info(f"removing media file {obj}")
        obj.delete()


def get_writer_options(job):
    word_options = [
        "highlight_words",
        "max_line_count",
        "max_line_width",
        "max_words_per_line",
    ]

    opts = {option: job.get(option) for option in word_options}

    # ensure word_timestamps is set if any of the word options are
    if job.get("word_timestamps") is None:
        for option in word_options:
            if job.get(option) is not None:
                opts["word_timestamps"] = True

    return opts


def get_aws(service_name):
    role = os.environ.get("AWS_ROLE_ARN")

    # This would be a lot easier if boto3 read AWS_ROLE_ARN like it does other
    # environment variables:
    #
    # see: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-api.html

    if role:
        sts_client = boto3.client("sts")
        response = sts_client.assume_role(
            RoleArn=role, RoleSessionName="speech-to-text"
        )
        cred = response["Credentials"]
        aws = boto3.resource(
            service_name,
            aws_access_key_id=cred["AccessKeyId"],
            aws_secret_access_key=cred["SecretAccessKey"],
            aws_session_token=cred["SessionToken"],
        )
    else:
        aws = boto3.resource(service_name)

    return aws


def get_bucket():
    s3 = get_aws("s3")
    bucket_name = os.environ.get("SPEECH_TO_TEXT_S3_BUCKET")
    return s3.Bucket(bucket_name)


def get_todo_queue():
    return get_queue(os.environ.get("SPEECH_TO_TEXT_TODO_SQS_QUEUE"))


def get_done_queue():
    return get_queue(os.environ.get("SPEECH_TO_TEXT_DONE_SQS_QUEUE"))


def get_queue(queue_name):
    sqs = get_aws("sqs")
    return sqs.get_queue_by_name(QueueName=queue_name)


def report_error(job, exception):
    """
    Add the job to the done queue with an error.
    """
    job["error"] = str(exception)
    queue = get_done_queue()
    logging.error("sending error message to done queue: {job}")
    queue.send_message(MessageBody=json.dumps(job))


def check_env():
    names = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "SPEECH_TO_TEXT_S3_BUCKET"]
    for name in names:
        if os.environ.get(name) is None:
            sys.exit(f"{name} is not defined in the environment")


def now():
    return datetime.datetime.now(datetime.UTC).isoformat()


def get_output_dir(job):
    path = Path(job["id"])
    if not path.is_dir():
        path.mkdir()

    return path


def create_job(media_path: Path, job_id: str = None, model: str = "small"):
    """
    Create a job for a given media file by placing the media file in S3 and
    sending a message to the TODO queue. This is really just for testing since
    the jobs are created by common-accessioning robot during captionWF.
    """
    job_id = str(uuid.uuid4()) if job_id is None else job_id
    add_media(media_path, job_id)

    job = {
        "id": job_id,
        "media": [
            media_path.name
        ],
        "options": {
            "model": model
        }
    }
    add_job(job)

    return job_id


def add_media(media_path, job_id):
    """
    Upload a media file to the bucket, and return the filename.
    """
    path = Path(media_path)
    key = f"media/{job_id}/{path.name}"

    bucket = get_bucket()
    logging.info(f"uploading {media_path} to s3://{bucket.name}/{key}")
    bucket.upload_file(media_path, key)

    return path.name


def add_job(job):
    """
    Create a job JSON file in the S3 bucket.
    """
    queue = get_todo_queue()
    queue.send_message(MessageBody=json.dumps(job))

    return


def receive_done_job():
    """
    Receives jobs on the DONE queue.
    """
    queue = get_done_queue()
    messages = queue.receive_messages(MaxNumberOfMessages=1)
    if len(messages) == 1:
        msg = messages[0]
        msg.delete()
        return json.loads(msg.body)
    elif len(messages) == 0:
        return None
    else:
        raise Exception("received more than one message from todo queue!")

@cache
def load_whisper_model(model_name):
    if torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"

    logging.info(f"loading {model_name} Whisper model for {device}")

    return whisper.load_model(model_name, download_root="whisper_models", device=device)


if __name__ == "__main__":
    check_env()

    parser = argparse.ArgumentParser(prog="speech_to_text")
    parser.add_argument("-c", "--create", help="Create a job for a given media file")
    parser.add_argument(
        "-r",
        "--receive-done",
        action="store_true",
        help="Retrieve a job from the done queue.",
    )
    parser.add_argument(
        "--job_id",
        action="store",
        dest="job_id",
        help="Provide a pre-determined job_id when --create mode is used to create a test job",
    )
    parser.add_argument(
        "-d",
        "--daemon",
        action="store_true",
        default=True,
        dest="daemon",
        help="Run forever looking for jobs",
    )
    parser.add_argument(
        "-n",
        "--no-daemon",
        action="store_false",
        default=False,
        dest="daemon",
        help="Run one job and exit.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="small",
        help="Create a job using a specific Whisper model"
    )
    args = parser.parse_args()

    if args.create:
        media_path = Path(args.create)
        if not media_path.is_file():
            logging.info(f"No such file {media_path}")

        job_id = create_job(media_path, args.job_id, args.model)
        logging.info(f"Created job {job_id} using {args.model}")

    elif args.receive_done:
        job = receive_done_job()
        if job is not None:
            logging.info(json.dumps(job, indent=2))
        else:
            logging.info("No messages were found in the todo queue...")

    else:
        main(daemon=args.daemon)
