FROM artefact.skao.int/ska-tango-images-pytango-builder:9.5.0 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.5.0 AS runtime
# The following COPY is required so that we actually build the buildenv stage.
# If we do not then as it is not at explicit requirement of the final target image it will be skipped.
# This manifests as an error on line 2 stating that `stage 'buildenv' must be defined before current stage 'runtime'`
COPY --from=buildenv . .
USER root

RUN make install-firmware

ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt install -y python3.11 python3.11-venv git \
    && python3.11 -m ensurepip \
    && python3.11 -m pip install --upgrade pip poetry \
    && poetry config virtualenvs.create false \
    && apt clean

RUN pip install -e .

USER tango
