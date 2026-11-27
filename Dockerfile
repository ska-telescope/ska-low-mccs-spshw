# Build stage. Both stages use the same python3.10, so the venv works in the runtime stage.
FROM artefact.skao.int/ska-python:1.1.5 AS build

ENV UV_PYTHON_DOWNLOADS=never

# git is only needed for dependencies from git branches.
RUN apt-get update && apt-get install -y --no-install-recommends git

WORKDIR /app
COPY download_firmware.sh ./
RUN ./download_firmware.sh

COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-install-project --no-dev --no-editable

COPY README.md ./
COPY src ./src
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev --no-editable


# Runtime stage.
FROM artefact.skao.int/ska-python:1.1.5

# The upgrade applies the Ubuntu fixes released after the base image.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# MccsTile loads the TPM firmware by name from its working directory.
WORKDIR /app
COPY --from=build /app/tpm_firmware_*.bit ./
COPY --from=build /app/.venv /app/.venv

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
