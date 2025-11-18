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

COPY README.md pyproject.toml poetry.lock* ./
RUN poetry install --no-root

COPY Makefile ./
COPY helmfile.d/ helmfile.d/
COPY .make/ .make/
RUN make install-firmware

COPY src ./
RUN poetry install