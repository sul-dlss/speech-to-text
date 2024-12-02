# speech-to-text

[![Test](https://github.com/sul-dlss/speech-to-text/actions/workflows/test.yml/badge.svg)](https://github.com/sul-dlss/speech-to-text/actions/workflows/test.yml)

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
docker run --rm --tty --env-file .env sul-speech-to-text --receive-done
```

## The Job Message Structure

The job is a JSON object (used as an SQS message payload) that contains information about how to run Whisper. Minimally it contains the Job ID and a list of S3 bucket file paths, which will be used to locate media files in S3 that need to be processed.

```json
{
  "id": "gy983cn1444",
  "media": [
    { "name": "gy983cn1444/media.mp4" }
  ]
}
```

The job id must be a unique identifier like a UUID. In some use cases a natural key could be used, as is the case in the SDR where druid-version is used.

## Whisper Options

You can also pass in options for Whisper, note that any options for how the transcript is serialized with a writer are given using the `writer` key:

```json
{
  "id": "gy983cn1444",
  "media": [
    { "name": "gy983cn1444/media.mp4" },
  ],
  "options": {
    "model": "large",
    "beam_size": 10,
    "writer": {
      "max_line_width": 80
    }
  }
}
```

If you are passing in multiple files and would like to specify different options for each file you can override at the file level. For example here two files are being transcribed, the first using French and the second in Spanish:

```json
{
  "id": "gy983cn1444",
  "media": [
    {
      "name": "gy983cn1444/media-fr.mp4",
      "options": {
        "language": "fr"
      }
    },
    {
      "name": "gy983cn1444/media-es.mp4",
      "options": {
        "language": "es"
      }
    }
  ],
  "options": {
    "model": "large",
    "beam_size": 10,
    "writer": {
      "max_line_width": 80
    }
  }
}
```

## Receiving Jobs

When a job completes you will receive a message on the DONE SQS queue which will contain JSON that looks something like:

```json
{
  "id": "gy983cn1444",
  "media": [
    {
      "name": "gy983cn1444/cat_videocat_video.mp4"
    },
    {
      "name": "gy983cn1444/The_Sea_otter.mp4",
      "language": "fr"
    }
  ],
  "options": {
    "model": "large",
    "beam_size": 10,
    "writer": {
      "max_line_count": 80
    }
  },
  "output": [
    "gy983cn1444/cat_video.vtt",
    "gy983cn1444/cat_video.srt",
    "gy983cn1444/cat_video.json",
    "gy983cn1444/cat_video.txt",
    "gy983cn1444/cat_video.tsv",
    "gy983cn1444/The_Sea_otter.vtt",
    "gy983cn1444/The_Sea_otter.srt",
    "gy983cn1444/The_Sea_otter.json",
    "gy983cn1444/The_Sea_otter.txt",
    "gy983cn1444/The_Sea_otter.tsv"
  ],
  "log": {
    "name": "whisper",
    "version": "20240930",
    "runs": [
      {
        "media": "gy983cn1444/cat_video.mp4",
        "transcribe": {
          "model": "large"
        },
        "write": {
          "max_line_count": 80,
          "word_timestamps": true
        }
      },
      {
        "media": "gy983cn1444/The_Sea_otter.mp4",
        "transcribe": {
          "model": "large",
          "language": "fr"
        },
        "write": {
          "max_line_count": 80,
          "word_timestamps": true
        }
      }
    ]
  }
}
```

If there was an error during processing the `output` will be an empty list, and an `error` property will be set to a message indicating what went wrong.

```json
{
  "id": "gy983cn1444",
  "media": [
    "gy983cn1444/cat_videocat_video.mp4",
    "gy983cn1444/The_Sea_otter.mp4"
  ],
  "options": {
    "model": "large",
    "beam_size": 10,
    "writer": {
      "max_line_count": 80
    }
  },
  "output": [],
  "error": "Invalid media file gy983cn1444/The_Sea_otter.mp4"
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

Note: the tests use the [moto](https://docs.getmoto.org/en/latest/) library to mock out AWS resources. If you want to test live AWS you can follow the steps above to create a job, run, and then receive the done message.
