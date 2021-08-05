#
# IMAGE_TO_TEST defines the tag of the Docker image to test
#
IMAGE_TO_TEST = $(CAR_OCI_REGISTRY_HOST)/$(DOCKER_REGISTRY_USER)/$(PROJECT):latest

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

pull:  ## download the application image
	docker pull $(IMAGE_TO_TEST)

interactive:  ## start an interactive session using the project image (caution: R/W mounts source directory to /app)
	docker run --rm -it --name=$(CONTAINER_NAME_PREFIX)dev \
		-e TANGO_HOST=$(TANGO_HOST) $(IMAGE_TO_TEST) /bin/bash

devimage:
	docker build --rm -f "Dockerfile" -t $(IMAGE_TO_TEST) .
