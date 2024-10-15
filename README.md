# speech-to-text

This repository contains a Docker configuration for performing serverless speech-to-text processing with Whisper using an Amazon Simple Storage Service (S3) bucket for media files, and Amazon Simple Queue Service (SQS) for coordinating work.

## Build

To build the container you will need to first download the pytorch models that Whisper uses. This is about 13GB of data and can take some time! The idea here is to bake the models into Docker image so they don't need to be fetched dynamically every time the container runs (which will add to the runtime). If you know you only need one size model, and want to just include that then edit the `whisper_models/urls.txt` file accordingly before running the `wget` command.

```shell
wget --directory-prefix whisper_models --input-file whisper_models/urls.txt
```

Then you can build the image:

```shell
docker build --tag sul-speech-to-text .
```

## Configure AWS

Create two queues, one for new jobs, and one for completed jobs:

```shell
$ aws sqs create-queue --queue-name sul-speech-to-text-todo-your-username
$ aws sqs create-queue --queue-name sul-speech-to-text-done-your-username
```

Create a bucket: 

```shell
aws s3 mb s3://sul-speech-to-text-dev-your-username
```

Configure `.env` with your AWS credentials so the Docker container can find them:

```shell
cp env-example .env
vi .env
```

## Run

### Create a Job

Usually common-accessioning robots will initiate new speech-to-text work by:

1. minting a new job ID
3. copying a media file to the S3 bucket
5. putting a job in the TODO queue

For testing you can simulate these things by running the Docker container with the `--create` flag. For example if you have a `file.mp4` file you'd like to create a job for you can:

```shell
docker run --rm --tty --volume .:/app --env-file .env sul-speech-to-text --create file.mp4
```

### Run the Job

Now you can run the container and have it pick up the job you placed into the queue. You can drop the `--gpus all` if you don't have a GPU.

```shell
docker run --rm --tty --env-file .env --gpus all sul-speech-to-text --no-daemon
```

Wait for the results to appear:

```shell
aws s3 ls s3://sul-speech-to-text-dev-your-username/out/${JOB_ID}/
```

Usually the message on the DONE queue will be processed by the captionWF in common-accessioning, but if you want you can pop messages off manually:

```shell
docker run --rm --tty --env-file .env sul-speech-to-text --receive
```

## The Job Message Structure

The job is a JSON object (used as an SQS message payload) that contains information about how to run Whisper. Minimally it contains the Job ID and a list of file names, which will be used to locate media files in S3 that need to be processed.

```json
{
  "id": "gy983cn1444-v2",
  "media": [
    "snl_tomlin_phone_company.mp4"
  ],
}
```

The job id must be a unique identifier like a UUID. In some use cases a natural key could be used, as is the case in the SDR where druid-version is used.

The worker will look in the configured S3 bucket for files to process at `"media/{job['id']}/{media_file}"` for each `media_file` in `job["media"]`. E.g. `gy983cn1444-v2/snl_tomlin_phone_company.mp4` for the above example JSON. You can see this illustrated in the `create_job` and `add_media` test functions in `speech_to_text.py`.

You can also pass in options for Whisper:

```json
{
  "id": "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F",
  "media": [
    "cat_video.mp4",
    "The_Sea_otter.mp4"
  ],
  "options": {
    "model": "large",
    "max_line_count": 80,
    "beam_size": 10
  }
}
```

When you receive the message on the DONE SQS queue it will contain the JSON:

```json
{
  "id": "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F",
  "media": ["bear_breaks_into_home_plays_piano_no_speech.mp4"],
  "options": {
    "model": "large",
    "max_line_count": 80,
    "beam_size": 10
  }
}
```  

## Testing

To run the tests it is probably easiest to create a virtual environment and run the tests with pytest:

```shell
python -mvenv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```
