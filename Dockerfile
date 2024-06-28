FROM artefact.skao.int/ska-tango-images-pytango-builder:9.4.3 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.4.3 AS runtime
# The following COPY is required so that we actually build the buildenv stage.
# If we do not then as it is not at explicit requirement of the final target image it will be skipped.
# This manifests as an error on line 2 stating that `stage 'buildenv' must be defined before current stage 'runtime'`
COPY --from=buildenv . .
USER root

RUN apt-get update && apt-get install -y git

RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

RUN poetry install --only main

USER tango
