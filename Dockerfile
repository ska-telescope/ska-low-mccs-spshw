FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.16 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.14 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
RUN ipython profile create

ENV PATH=/home/tango/.local/bin:$PATH

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

USER root

RUN python3 -m pip install poetry
#RUN python3 -m poetry config virtualenvs.in-project true
RUN poetry config virtualenvs.create false

COPY ./poetry.lock ./pyproject.toml ./pyfabil-1.0-py3-none-any.whl ./

RUN poetry install --no-dev 
