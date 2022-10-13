FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32 AS buildenv
RUN apt-get update && apt-get install gnupg2 -y

USER root

ENV POETRY_HOME="/opt/poetry"
ENV PATH="$POETRY_HOME/bin:$PATH"

RUN python3 -m pip install poetry
RUN poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
COPY ./pyfabil-1.0-py3-none-any.whl ./aavs_system-1.0-py3-none-any.whl ./

# Install DAQ pre-reqs
COPY aavs-system/ ./aavs-system/
WORKDIR ./aavs-system
RUN apt-get install -y libcap2-bin
#RUN setcap cap_net_raw,cap_ipc_lock,cap_sys_nice,cap_sys_admin,cap_kill+ep /usr/bin/python3.7
RUN ["/bin/bash", "-c", "source cmake -DCMAKE_INSTALL_PREFIX=."]
RUN ["/bin/bash", "-c", "source make install"]

WORKDIR .

# Setup DAQ Core.
#WORKDIR /workspaces/ska-low-mccs/aavs-daq/src/
#RUN mkdir build && cmake -DCMAKE_INSTALL_PREFIX=/ && make install

# Setup AAVS DAQ
#WORKDIR /workspaces/ska-low-mccs/aavs-system/src/
#RUN mkdir build && cmake -DCMAKE_INSTALL_PREFIX=/ -DDAQ_DIRECTORY=/ -DWITH_CORRELATOR=OFF

# Install PyDaq library.
#WORKDIR /workspaces/ska-low-mccs/aacs-system/python/
#RUN ["python3", "setup.py", "install"]

#WORKDIR .

RUN poetry install -vvv

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
