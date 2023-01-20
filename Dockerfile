FROM artefact.skao.int/ska-tango-images-pytango-builder:9.3.32 AS buildenv
FROM artefact.skao.int/ska-tango-images-pytango-runtime:9.3.19 AS runtime

# create ipython profile to so that itango doesn't fail if ipython hasn't run yet
#RUN ipython profile create
USER root

ENV AAVS_SYSTEM_SHA=5502db425dd9939bd33d3932928d76730d8abe35
ENV PYFABIL_SHA=a82e19918145a7a1a6daec920d112ec27dd1ca99

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive TZ="United_Kingdom/London" apt-get install -y \
    git pip
    
RUN git clone https://gitlab.com/ska-telescope/aavs-system.git /app/aavs-system/
WORKDIR /app/aavs-system
RUN git reset --hard ${AAVS_SYSTEM_SHA}
RUN pip install git+https://lessju@bitbucket.org/lessju/pyfabil.git@$PYFABIL_SHA --force-reinstall

#move all bit files to a folder where pyfabil looks
WORKDIR /app/
COPY *.bit /app/aavs-system/

RUN poetry config virtualenvs.create false
RUN poetry install --only main
USER tango
