import os
import boto3
import json
from pathlib import Path

import moto
import pytest
import speech_to_text

BUCKET = "bucket"
TODO_QUEUE = "todo"
DONE_QUEUE = "done"


@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["SPEECH_TO_TEXT_TODO_SQS_QUEUE"] = TODO_QUEUE
    os.environ["SPEECH_TO_TEXT_DONE_SQS_QUEUE"] = DONE_QUEUE
    os.environ["SPEECH_TO_TEXT_S3_BUCKET"] = BUCKET


@pytest.fixture
def sts(aws_credentials):
    with moto.mock_aws():
        yield boto3.client("sts")


@pytest.fixture
def s3(aws_credentials):
    with moto.mock_aws():
        yield boto3.client("s3")


@pytest.fixture
def sqs(aws_credentials):
    with moto.mock_aws():
        yield boto3.resource("sqs")


@pytest.fixture
def bucket(s3):
    return s3.create_bucket(Bucket=BUCKET)


@pytest.fixture
def queues(sqs):
    sqs.create_queue(QueueName=TODO_QUEUE)
    sqs.create_queue(QueueName=DONE_QUEUE)


# ignore utcnow warning until https://github.com/boto/boto3/issues/3889 is resolved
@pytest.mark.filterwarnings("ignore:datetime.datetime.utcnow")
def test_speech_to_text(bucket, queues):
    job_id = speech_to_text.create_job(
        Path("tests/data/en.wav"),
        options={"model": "small", "writer": {"max_line_width": 42}},
    )

    speech_to_text.main(daemon=False)

    # check that the vtt file is present
    test_bucket = speech_to_text.get_bucket()
    vtt_file = test_bucket.Object(f"{job_id}/output/en.vtt").get()
    assert vtt_file, "vtt file created"
    assert "This is a test" in vtt_file["Body"].read().decode("utf-8"), "vtt content"

    # check that the job file is in the bucket and has the list of files in output
    job_file = test_bucket.Object(f"{job_id}/job.json").get()
    assert job_file, "job file created"
    job = json.loads(job_file["Body"].read().decode("utf-8"))
    assert len(job["output"]) == 5
    assert f"{job_id}/output/en.vtt" in job["output"]
    assert f"{job_id}/output/en.srt" in job["output"]
    assert f"{job_id}/output/en.txt" in job["output"]
    assert f"{job_id}/output/en.tsv" in job["output"]
    assert f"{job_id}/output/en.json" in job["output"]

    # check that max_line_width took effect on the writer options that were used
    assert (
        job["extraction_technical_metadata"]["effective_writer_options"][
            "max_line_width"
        ]
        == 42
    )

    # make sure there's a message in the "done" queue
    queue = speech_to_text.get_done_queue()
    msgs = queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=10)
    assert len(msgs) == 1, "found a done message"
    assert msgs[0].delete(), "delete the message from the queue"

    # make sure the job looks ok
    job = json.loads(msgs[0].body)
    assert job["id"] == job_id
    assert job["finished"]
    assert len(job["output"]) == 5
    assert f"{job_id}/output/en.vtt" in job["output"]
    assert f"{job_id}/output/en.srt" in job["output"]
    assert f"{job_id}/output/en.txt" in job["output"]
    assert f"{job_id}/output/en.tsv" in job["output"]
    assert f"{job_id}/output/en.json" in job["output"]

    jobs = queue.receive_messages(MaxNumberOfMessages=1)
    assert len(jobs) == 0, "queue empty"
