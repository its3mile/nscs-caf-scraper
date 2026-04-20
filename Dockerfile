ARG BASE_IMAGE=mcr.microsoft.com/playwright/python:v1.58.0-noble
FROM $BASE_IMAGE

RUN DEBIAN_FRONTEND=noninteractive \
    && apt-get update \ 
    && apt-get install -y build-essential --no-install-recommends curl ca-certificates

ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

COPY . /app

ENV UV_NO_DEV=1

WORKDIR /app

RUN uv sync --locked

CMD ["uv", "run", "main.py"]
