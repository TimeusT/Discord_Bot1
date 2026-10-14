FROM python:3.12-slim

# ffmpeg lets the bot shrink videos that are too big for Discord's upload limit.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# /data holds everything that must survive restarts: the chosen channels and the
# downloaded speech-to-text model.
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    HF_HOME=/data/huggingface

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Run as a normal user instead of root.
RUN useradd --create-home bot && mkdir /data && chown bot /data
USER bot

CMD ["python", "-m", "placebot"]
