FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.16 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y
#RUN ln -s /usr/bin/python3 /usr/bin/python3

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"
ENV POETRY_VERSION="1.1.12"

RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock* ./pyfabil-1.0-py3-none-any.whl ./
RUN poetry config virtualenvs.create true \
    && poetry install --no-root -vvv

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
