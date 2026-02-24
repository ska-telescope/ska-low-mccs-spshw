FROM artefact.skao.int/ska-tango-images-tango-dsconfig:1.8.3 AS tools
FROM artefact.skao.int/ska-python:0.2.5 AS runtime

WORKDIR /app

COPY --from=tools /usr/local/bin/retry /usr/local/bin/retry
COPY --from=tools /usr/local/bin/wait-for-it.sh /usr/local/bin/wait-for-it.sh

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install git for dependencies from git repositories
RUN apt-get update && apt-get install -y --no-install-recommends git make curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-install-project --no-dev

# COPY Makefile ./
# COPY helmfile.d/ helmfile.d/
# COPY .make/ .make/
COPY . .
RUN make install-firmware
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev