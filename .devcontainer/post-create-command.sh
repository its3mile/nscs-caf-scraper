#!/bin/sh
# set -eu
#
# This script executes once the dev container is created from the build image, in the container
#

# Echo uv version.
uv --version

# Create/sync development environment
echo "Create/sync development environment"
uv sync

# Install Git pre-commit hooks
echo "Installing Git pre-commit hooks."
uv tool install pre-commit
pre-commit install
