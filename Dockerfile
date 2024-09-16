FROM ubuntu:22.04

ENV AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID
ENV AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
ENV AWS_REGION=$AWS_REGION
ENV AWS_ROLE_ARN=$AWS_ROLE_ARN
ENV SPEECH_TO_TEXT_S3_BUCKET=$SPEECH_TO_TEXT_S3_BUCKET

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    sudo \
    python3.11 \
    python3-distutils \
    python3-pip \
    ffmpeg

WORKDIR /app

ADD ./whisper_models whisper_models
ADD ./requirements.txt requirements.txt

RUN python3.11 -m pip install --upgrade pip
RUN python3.11 -m pip install -r requirements.txt

ADD ./speech_to_text.py speech_to_text.py

CMD ["python3.11", "speech_to_text.py", "--daemon"]
