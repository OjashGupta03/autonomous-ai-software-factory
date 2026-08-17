# The isolated execution image (docs/11-code-execution-sandbox.md).
#
# This image is intentionally NOT part of docker-compose's long-running
# services - the backend/worker build it once (`docker build -f
# docker/sandbox.Dockerfile -t factory-sandbox:latest .`) and then the
# Docker SDK (app/sandbox/docker_executor.py) launches short-lived,
# resource-limited containers from it on demand, one per tool call that
# needs to actually execute something (tests, lint, format, shell).
#
# Deliberately generic (Python + Node.js in one image) rather than one
# image per language, since a single project can contain both a FastAPI
# backend and a React frontend that both need testing/linting - see
# docs/23-design-decisions.md for the tradeoff (a fatter image vs. two
# images and cross-image workspace handoff).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest pytest-asyncio black ruff \
    && npm install -g prettier eslint

# Non-root user - the executor also sets cap_drop=ALL and
# security_opt=no-new-privileges at container-run time; this is the
# in-image half of that same defense-in-depth story.
RUN useradd --create-home --uid 1000 sandbox
USER sandbox
WORKDIR /workspace

# No CMD/ENTRYPOINT - docker_executor.py always supplies an explicit
# argv command per run (e.g. ["pytest", "-q"]); there is no default
# process this image starts on its own.
