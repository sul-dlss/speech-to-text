FROM nvidia/cuda:12.8.0-cudnn-devel-ubuntu22.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    ca-certificates \
    python3 \
    python3-dev \
    python3-pip \
    ffmpeg

# download and install uv
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

ADD ./whisper_models whisper_models
ADD ./pyproject.toml pyproject.toml
ADD ./uv.lock uv.lock
ADD ./error_reporting_wrapper.py error_reporting_wrapper.py
ADD ./speech_to_text.py speech_to_text.py

# save on startup time by pre-compiling all the dependencies
RUN uv run python3 -m py_compile speech_to_text.py

ENTRYPOINT ["uv", "run", "error_reporting_wrapper.py", "python3", "speech_to_text.py"]
