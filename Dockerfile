FROM nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-dev \
    python3-distutils \
    python3-pip \
    ffmpeg

WORKDIR /app

ADD ./whisper_models whisper_models
ADD ./pyproject.toml pyproject.toml

RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install uv

ADD ./error_reporting_wrapper.py error_reporting_wrapper.py

ADD ./speech_to_text.py speech_to_text.py
RUN uv run python3 -m py_compile speech_to_text.py

ENTRYPOINT ["uv", "run", "error_reporting_wrapper.py", "python3", "speech_to_text.py"]
