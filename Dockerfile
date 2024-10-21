FROM python:3.12.5-bookworm

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY . /mnt/build/

WORKDIR /mnt/build

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 setup.py sdist && \
    cd / && \
    rm -rf /mnt/build

WORKDIR /