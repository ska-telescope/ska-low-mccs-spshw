FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main

COPY --chown=tango:tango . .

USER tango
