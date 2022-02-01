FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.10 AS buildenv

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create
ENV PATH=/home/tango/.local/bin:$PATH

RUN python3 -m pip install poetry
RUN python3 -m poetry config virtualenvs.in-project true

COPY ./poetry.lock ./pyproject.toml ./pyfabil-1.0-py3-none-any.whl ./
# TODO: This poetry install (and the one below) should be --no-dev too, but at the
# moment we are using this image to run our functional test.
RUN python3 -m poetry install --no-root

COPY . .
RUN python3 -m poetry install

FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.10 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create

COPY --from=buildenv --chown=tango:tango /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
