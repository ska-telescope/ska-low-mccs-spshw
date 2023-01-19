FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.19 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
#RUN ipython profile create
USER root

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive TZ="United_Kingdom/London" apt-get install -y \
    build-essential ca-certificates cmake libcap2-bin git make tzdata
    
ENV AAVS_SYSTEM_SHA=5502db425dd9939bd33d3932928d76730d8abe35
ENV PYFABIL_SHA=21a9ac02a75322486c2b23472bdd9efca01643ca

RUN poetry config virtualenvs.create false

RUN git clone https://gitlab.com/ska-telescope/aavs-system.git /app/aavs-system/
WORKDIR /app/aavs-system
RUN git reset --hard ${AAVS_SYSTEM_SHA}

#Replace and run a deploy script without DAQ!
RUN cp /app/deploy.sh /app/aavs-system/
RUN ["/bin/bash", "-c", "source /app/aavs-system/deploy.sh"]

RUN poetry install --only main
RUN setcap cap_net_raw,cap_ipc_lock,cap_sys_nice,cap_sys_admin,cap_kill+ep /usr/bin/python3.10

USER tango
