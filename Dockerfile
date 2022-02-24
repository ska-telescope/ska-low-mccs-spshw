FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.27 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.14 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
#RUN ipython profile create

USER root

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python -
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.0-py3-none-any.whl ./aavs_system-1.0-py3-none-any.whl ./

RUN poetry install --no-dev -vvv

USER tango
