#!/bin/bash

# The following environment variables will need to be set in order to push the
# new speech-to-text Docker image:
#
# - AWS_ACCESS_KEY_ID: the access key for the speech-to-text user
# - AWS_SECRET_ACCESS_KEY: the secret key for the speech-to-text user
# - AWS_ECR_DOCKER_REPO: the Elastic Compute Registry URL for the Docker repository
#
# The values can be obtained by running `terraform output` in the relevant portion of
# the Terraform configuration.

# Exit immediately if something doesn't work

set -e

# Download the Whisper large-v3 model, which is what we use by default. Building
# the image with the model in it already will speed up processing since whisper
# won't need to pull it dynamically.

wget --timestamping --directory whisper_models https://openaipublic.azureedge.net/main/whisper/models/e5b1a55b89c1367dacf97e3e19bfd829a01529dbfdeefa8caeb59b3f1b81dadb/large-v3.pt 

# Log in to ECR

aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $AWS_ECR_DOCKER_REPO

# Build the image for Linux (not really needed when running in Github Actions)

docker build -t speech-to-text --platform="linux/amd64" .

# Tag and push the image to ECR

docker tag speech-to-text $AWS_ECR_DOCKER_REPO

docker push $AWS_ECR_DOCKER_REPO
