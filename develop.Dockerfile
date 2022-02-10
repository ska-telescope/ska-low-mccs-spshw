FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.16 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y
#RUN ln -s /usr/bin/python /usr/bin/python3

ENV PATH=/home/tango/.local/bin:$PATH

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
#ENV POETRY_VERSION="1.1.12"

USER root

#RUN pip install "poetry==$POETRY_VERSION"
RUN python3 -m pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.0-py3-none-any.whl ./aavs_system-1.0-py3-none-any.whl ./
#RUN poetry config virtualenvs.create true \
#    && poetry install --no-root -vvv
RUN poetry install

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
