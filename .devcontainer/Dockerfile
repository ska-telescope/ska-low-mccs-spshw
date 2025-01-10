FROM artefact.skao.int/ska-build-python:0.1.1 AS build
RUN apt-get update && apt-get install git gnupg2 graphviz openssh-client plantuml -y

ENV TZ="United_Kingdom/London"
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get install software-properties-common -y
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get install -y python3.11 
#&& update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2

RUN useradd --create-home --home /home/vscoder --shell /bin/bash vscoder
USER vscoder

RUN pipx ensurepath && pipx install poetry

#ENV LC_ALL en_US.UTF-8
