FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.27 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y

USER root

RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python -
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.0-py3-none-any.whl ./aavs_system-1.0-py3-none-any.whl ./

RUN poetry install -vvv

#USER tango

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
