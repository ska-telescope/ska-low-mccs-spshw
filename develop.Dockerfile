FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.13 AS buildenv
RUN apt-get update && apt-get install ca-certificates gnupg2 -y

COPY requirements-dev.txt ./

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements-dev.txt && \
    rm ./requirements-dev.txt

ARG UID
ARG GID

ENV GROUP_ID=${GID:-0}
ENV USER_ID=${UID:-0}

ENV USER=${UID:+user}
ENV USER=${USER:-root}

RUN if [ "$USER" != "root" ] ; then \
    addgroup --gid ${GROUP_ID} ${USER} ; \
    adduser --disabled-password --gecos '' --uid ${USER_ID} --gid ${GROUP_ID} ${USER} ; \
    fi
USER ${USER}
