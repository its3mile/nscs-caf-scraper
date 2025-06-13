ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/python:3.12
FROM $BASE_IMAGE

RUN DEBIAN_FRONTEND=noninteractive \
    && apt-get update \ 
    && apt-get install -y build-essential --no-install-recommends make \
    ca-certificates \
    git \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    curl \
    unzip \
    llvm \
    libncurses5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    firefox-esr \
    binfmt-support \
    qemu-user-static

RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz \
    && tar -xzvf geckodriver-v0.35.0-linux64.tar.gz \
    && mv geckodriver /usr/local/bin/geckodriver \
    && rm geckodriver-v0.35.0-linux64.tar.gz
