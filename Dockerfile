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

# Next steps in order from least-to-most frequently changing for caching
# Download and install TPM firmware.
# .make and .helmfile.d are required for make to run - should be fixed
COPY .make/ .make/
COPY .make-uv/ .make-uv/
COPY helmfile.d/ helmfile.d/
COPY Makefile ./
RUN make install-firmware

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-install-project --no-dev

# Copy source code and install local project
COPY . .
RUN --mount=from=ghcr.io/astral-sh/uv,source=/uv,target=/bin/uv \
    uv sync --locked --no-dev
