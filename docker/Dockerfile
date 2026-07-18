# Build a container for a VForge agent application.
#
# Usage (from the repository root):
#   docker build -f docker/Dockerfile -t my-agent --build-arg APP_DIR=examples/assistant .
#   docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... my-agent

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/vforge

# Install the framework
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Copy the agent application (application.yaml, prompts/, skills/)
ARG APP_DIR=examples/assistant
COPY ${APP_DIR} /app
WORKDIR /app

EXPOSE 8000
CMD ["vforge", "start"]
