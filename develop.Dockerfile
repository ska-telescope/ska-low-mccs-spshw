FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y

USER root

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN python3 -m pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.1-py3-none-any.whl ./aavs_system-1.1-py3-none-any.whl ./

RUN poetry install --only main

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
