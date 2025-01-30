# speech-to-text

[![Test](https://github.com/sul-dlss/speech-to-text/actions/workflows/test.yml/badge.svg)](https://github.com/sul-dlss/speech-to-text/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/sul-dlss/speech-to-text/graph/badge.svg?token=SB8E3KXTJ1)](https://codecov.io/gh/sul-dlss/speech-to-text)

This repository contains a Docker configuration for performing speech-to-text processing with [Whisper](https://openai.com/index/whisper/) using Amazon Web Services (AWS) to provision GPU resources on demand, and to tear them down when there is no more remaining work. It uses:

* [AWS S3](https://aws.amazon.com/s3/): to store media in need of transcription and the transcription results.
* [AWS Batch](https://aws.amazon.com/batch/): manages a work queue and provisioning EC2 instances.
* [AWS SQS](https://aws.amazon.com/sqs/): for receiving a notification when work is completed.
* [AWS ECR](https://aws.amazon.com/ecr/): a Docker repository to store the code in this Git repository.

## Configure AWS

We have a [Terraform](https://www.terraform.io/) configuration in [dlss/terraform-aws](https://github.com/sul-dlss/terraform-aws/tree/main/organizations/development/speech_to_text] for provisioning AWS resources. If you aren't at Stanford Libraries and would like to use it as a reference Terraform implementation please get in touch via the [issue tracker](https://github.com/sul-dlss/speech-to-text/issues). Once you have the configuration and have installed Terraform you can:

```shell
$ terraform validate
$ terraform apply
```

This will set up an S3, Batch, SQS and ECR and create an AWS user with permission to interact with these services. 

## Build and Deploy

In order to use the service, you will need to build and deploy the speech-to-text Docker image to ECR, where it will be picked up by Batch. You can use the provided `deploy.sh` script to build and deploy.

Before running it you will need to define three environment variables using the values that Terraform has created for you, which you can inspect by running `terraform output`:

```
$ terraform output

batch_job_definition = "arn:aws:batch:us-west-2:1234567890123:job-definition/speech-to-text-dev"
batch_job_queue = "arn:aws:batch:us-west-2:1234567890123:job-queue/speech-to-text-dev"
docker_repository = "1234567890123.dkr.ecr.us-west-2.amazonaws.com/speech-to-text-dev"
ecs_instance_role = "speech-to-text-dev-ecs-instance-role"
s3_bucket = "arn:aws:s3:::speech-to-text-dev"
sqs_done_queue = "https://sqs.us-west-2.amazonaws.com/1234567890123/speech-to-text-dev"
speech_to_text_access_key_id = "XXXXXXXXXXXXXX"
speech_to_text_secret_access_key = <sensitive>

$ terraform output speech_to_text_secret_access_key
"XXXXXXXXXXXXXXXXXXXXXXXX"
```

You will want to set these in your environment:

- AWS_ACCESS_KEY_ID: the `speech_to_text_access_key_id` value
- AWS_SECRET_ACCESS_KEY: the `speech_to_text_secret_access_key`
- AWS_ECR_DOCKER_REPO: the `docker_repository` value
- AWS_DEFAULT_REGION: e.g. `us-west-2`
- DEPLOYMENT_ENV: the SDR environment being deployed to (e.g. qa, staging, production)
- HONEYBADGER_API_KEY: the API key for this project, to support deployment notifications (obtainable from project settings in HB web UI)

Then you can run the deploy:

```bash
$ ./deploy.sh
```

Since this project already installs the `python-dotenv` package, you can also do something like the following to run the deploy script with the correct environment variable values, if you want to avoid pasting credentials into your terminal and/or having them stored in your shell history:

```shell
# requires you to create a .env.qa file with the QA-specific env vars values needed by deploy.sh
dotenv --file=.env.deploy.qa run ./deploy.sh
```

## Run

### Upload Media

In order to use speech-to-text you need to upload your media files to the Amazon S3 bucket that was created. You should mint a unique job identifier for your job, and use that identifier as a prefix when uploading your file. So for example if your job ID is `gy983cn1444`:

```
aws s3 cp my-media.mp3 s3://speech-to-text-example/gy983cn1444/my-media.mp3
```

### Create a Job

#### The Job Message Structure

The speech-to-text job is a JSON object that contains information about how to run Whisper. Minimally it contains the Job ID and a list of S3 bucket file paths, which will be used to locate media files in S3 that need to be processed.

```json
{
  "id": "gy983cn1444",
  "media": [
    { "name": "gy983cn1444/media.mp4" }
  ]
}
```

The job id must be a unique identifier like a UUID. In some use cases a natural key could be used, as is the case in the SDR where druid-version is used.

#### Whisper Options

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

You need to send this JSON to the Batch queue:

```shell
$ aws batch submit-job \
  --job-name gy983cn1444 \
  --job-queue "arn:aws:batch:us-west-2:1234567890123:job-queue/speech-to-text-dev" \
  --job-definition arn:aws:batch:us-west-2:1234567890123:job-definition/speech-to-text-dev" \
  --parameters 'job=<JOB JSON>'
```

## Receiving Jobs

When a job completes you will receive a message on the SQS queue by doing something like:

```shell
$ aws sqs receive-message --queue-url "https://sqs.us-west-2.amazonaws.com/1234567890123/speech-to-text-dev"
```

Note: be sure that your code removes the received messages from the queue or else they will reappear! 

The message you receive will be some JSON that looks something like your job,
but includes an `output` stanza with a list of transcript files that were
created.

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

You can then use an AWS S3 client to download the transcripts given in the `output` JSON stanza:

```shell
$ aws s3 cp s3://gy983cn1444/cat_video.vtt cat_video.vtt
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

## Manually Running a Job

We don't actually interact with the speech-to-text service using the awscli utility at the command line. Instead the speech-to-text service is used by our digital repository, in our case the [common-accessioning](https://github.com/sul-dlss/common-accessioning)) system, which interacts directly with AWS using a Ruby AWS client. If you would like to simulate this yourself you can run the `speech_to_text.py` with the `--create` and `--done` flags.

First you will need a `.env` file that tells `speech_to_text.py` your AWS credentials and some of the resources that Terraform configured for you.

```
cp env-example .env
```

Then replace the `CHANGE_ME` values in the `.env` file. You can use `terraform output` to determine the names for AWS resources like the S3 bucket, the region, and the queues.

Then you are ready to create a job. Here a job is being created for the `file.mp4` media file:

```shell
python speech_to_text.py --create file.mp4
```

This will:

1. Mint a Job ID.
2. Upload `file.mp4` to the S3 bucket.
3. Send the job to AWS Batch using some default Whisper options.

Then you can check periodically to see if the job is completed by running:

```shell
python speech_to_text.py --done
```

This will:

1. Look for a done message in the SQS queue.
2. Delete the message from the queue so it isn't picked up again.
3. Print the received finished job JSON.
3. Download the generated transcript files from the S3 bucket to the current working directory.

## Testing

To run the tests it is probably easiest to create a virtual environment and run the tests with pytest:

```shell
python -mvenv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

If you've already installed dependencies in your current virtual env, and want to update to the latest versions:
```shell
pip install --upgrade -r requirements.txt
```

Note: the tests use the [moto](https://docs.getmoto.org/en/latest/) library to mock out AWS resources. If you want to test live AWS you can follow the steps above to create a job, run, and then receive the done message.

You may need to install `ffmpeg` on your laptop in order to run the tests.  On a Mac, see if you have the dependency installed:

`which ffprobe`

If you get no result, install with:

`brew install ffmpeg`

### Test coverage reporting

In addition to the terminal display of a summary of the test coverage percentages, you can get a detailed look at which lines are covered or not by opening `htmlcov/index.html` after running the test suite.

## Continuous Integration

This Github repository is set up with a Github Action that will automatically deployed tagged releases e.g. `rel-2025-01-01` to the DLSS development and staging AWS environments. When a Github release is created it will automatically be deployed to the production AWS environment.

## Development Notes

When updating the base Docker image, in order to prevent random segmentation faults you will want to make sure that:

1. You are using an [nvidia/cuda](https://hub.docker.com/r/nvidia/cuda) base Docker image.
2. The version of CUDA you are using in the Docker container aligns with the version of CUDA that is installed in the host operating system that is running Docker.

## Benchmarking

It may be useful to compare the output of speech-to-text with previous runs. See docs/README.md for more about that.

## Linting and Type Checking

You may notice your changes fail in CI if they require reformatting or fail type checking. We use [ruff](https://docs.astral.sh/ruff/) for formatting Python code, and [mypy](https://mypy-lang.org/) for type checking. Both of those should be present in your virtual environment.

Check your code:

```shell
ruff check
```

If you want to reformat your code you can:

```shell
ruff format .
```

If you would prefer to see what would change you can:

```shell
ruff format --check . # just tells you that things would change, e.g. "1 file would be reformatted, 4 files already formatted"
ruff format --diff .  # if files would be reformatted: print the diff between the current file and the re-formatted file, then exit with non-zero status code
```

Similarly if you would like to see if there are any type checking errors you can:

```shell
mypy .
```

One line for running the linter, the type checker, and the test suite (failing fast if there are errors):
```shell
ruff format --diff . && ruff check && mypy . && pytest
```
