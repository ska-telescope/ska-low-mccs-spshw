FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.19 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
#RUN ipython profile create

USER root

RUN python3 -m pip install poetry
#RUN poetry update
#RUN poetry env use 3.10
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.0-py3-none-any.whl ./aavs_system-1.0-py3-none-any.whl ./

#RUN poetry install --no-dev -vvv (Deprecated)
RUN poetry install --only main

USER tango
