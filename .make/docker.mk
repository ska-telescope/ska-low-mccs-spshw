#
# IMAGE_TO_TEST defines the tag of the Docker image to test
#
IMAGE_TO_TEST = $(DOCKER_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT):latest

#
# Never use the network=host mode when running CI jobs, and add extra
# distinguishing identifiers to the network name and container names to
# prevent collisions with jobs from the same project running at the same
# time.
#
ifneq ($(CI_JOB_ID),)
CONTAINER_NAME_PREFIX := $(PROJECT)-$(CI_JOB_ID)-
else
CONTAINER_NAME_PREFIX := $(PROJECT)-
endif

#
# Defines a default make target so that help is printed if make is called
# without a target
#
.DEFAULT_GOAL := help

#
# defines a function to copy the ./test-harness directory into the container
# and then runs the requested make target in the container. The container is:
#
#   1. attached to the network of the docker-compose test system
#   2. uses a persistent volume to cache Python eggs and wheels so that fewer
#      downloads are required
#   3. uses a transient volume as a working directory, in which untarred files
#      and test output can be written in the container and subsequently copied
#      to the host
#
test lint:
	@echo "Disabled - use native tox build"

pull:  ## download the application image
	docker pull $(IMAGE_TO_TEST)

interactive:  ## start an interactive session using the project image (caution: R/W mounts source directory to /app)
	docker run --rm -it --name=$(CONTAINER_NAME_PREFIX)dev  -e TANGO_HOST=$(TANGO_HOST) $(IMAGE_TO_TEST) /bin/bash

devimage:
	docker build --rm -f "Dockerfile" -t $(IMAGE_TO_TEST) .
