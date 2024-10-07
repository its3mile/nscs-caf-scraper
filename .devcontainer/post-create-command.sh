#!/bin/sh
# set -eu
#
# This script executes once the dev container is created from the build image, in the container
#

# Echo poetry version.
poetry --version

# Disable poetry virtualenv - as it is running in a devcontainer already.
poetry config virtualenvs.create false

# Install project dependencies.
echo "Installing project dependencies."
poetry install

# Install pre-commit hooks
echo "Installing Git pre-commit hooks."
pre-commit install