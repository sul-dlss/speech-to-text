# speech-to-text

This repository contains a Docker configuration for performing serverless speech-to-text processing with Whisper using an Amazon S3 bucket for coordinating work.

## Build

To build the container you will need to first download the pytorch models that Whisper uses. This is about 13GB of data and can take some time! The idea here is to have the container come with the models baked in, so it doesn't need to fetch them dynamically every time the container runs. If you know you only need one size model, and want to just include that then edit the `whisper_models/urls.txt` file accordingly before running the `wget` command.

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
$ aws sqs create-queue --queue-name sul-speech-to-text-todo
$ aws sqs create-queue --queue-name sul-speech-to-text-done
```

Create a bucket: 

```shell
aws s3 mb s3://sul-speech-to-text
```

Configure `.env` with your AWS credentials so the Docker container can find them:

```shell
cp env-example .env
vi .env
```

## Create a Job

Typically common-accessioning robots will initiate new work by:

1. minting a new job ID
2. copying the media file to the S3 bucket
3. putting a job in the TODO queue.

For testing you can simulate these things by running:

```shell
python3 speech_to_text.py create
```

## Run

Now you can run the container and have it pick up the job you placed into the queue:

```shell
docker run --env-file .env sul-speech-to-text
```

Wait for the results to appear:

```shell
aws ls s3://sul-speech-to-text/out/${JOB_ID}/
```

## The Job File

The job file is a JSON object that contains information about how to run Whisper. Minimally it contains the Job ID,  and what media files to process using the service defaults:

```json
{
  "id": "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F",
  "druid": "gy983cn1444",
  "media": [
    "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F.mp4"
  ]
}
```

You can also pass in options for Whisper:

```json
{
  "id": "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F",
  "druid": "gy983cn1444",
  "media": [
    "8EB51B59-BDFF-4507-B1AA-0DE91ACA388F.mp4"
  ],
  "options": {
    "model": "large",
    "max_line_count": 80,
    "beam_size": 10
  }
}
```

## Testing

To run the tests you want to:

Create a virtual environment, and activate it:

```shell
python -mvenv .venv
source .venv/bin/activate
```

Install the dependencies:

```shell
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Run the tests, which will also build and run the Docker container:

```shell
pytest
```
