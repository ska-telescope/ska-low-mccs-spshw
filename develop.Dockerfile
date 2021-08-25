FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.10 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | python3 - && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./pyfabil-1.0-py3-none-any.whl ./
RUN poetry install --no-root -vvv


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
