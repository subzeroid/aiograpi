FROM python:3.12.8-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /mnt/build

COPY . ./

# Binaries required by aiograpi for video uploads
RUN apt-get update -y \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        mpv

# Install aiograpi dependencies and clean up the image
RUN pip install --no-cache-dir -r requirements.txt \
    && python3 setup.py install \
    && cd / \
    && rm -rf /mnt/build \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /