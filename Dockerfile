# TODO: Adding this image "as tools"
# so that we can copy the shell scripts
# that ska-tango-util expects this image to have
# is highly unsatisfactory.
# I've taken this from ska-tango-examples
# but hopefully a better solution will be found.
FROM artefact.skao.int/ska-tango-images-tango-dsconfig:1.5.13 AS tools
FROM artefact.skao.int/ska-build-python:0.1.1

# TODO: Unsatisfactory; see comment above
COPY --from=tools /usr/local/bin/retry /usr/local/bin/retry
COPY --from=tools /usr/local/bin/wait-for-it.sh /usr/local/bin/wait-for-it.sh
WORKDIR /src
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV POETRY_VIRTUALENVS_CREATE=1
ENV VIRTUAL_ENV=/src/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV TZ="United_Kingdom/London"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get install -y python3.11
# && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2
COPY README.md pyproject.toml poetry.lock* ./
RUN poetry install --no-root
COPY src ./
RUN poetry install