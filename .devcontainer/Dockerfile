FROM nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest AS buildenv
RUN apt-get update && apt-get install gnupg2 -y

COPY requirements-dev.txt ./

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements-dev.txt
