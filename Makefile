#
# Project makefile for a Tango project. You should normally only need to modify
# DOCKER_REGISTRY_USER and PROJECT below.
#

#
# DOCKER_REGISTRY_HOST, DOCKER_REGISTRY_USER and PROJECT are combined to define
# the Docker tag for this project. The definition below inherits the standard
# value for DOCKER_REGISTRY_HOST (=rnexus.engageska-portugal.pt) and overwrites
# DOCKER_REGISTRY_USER and PROJECT to give a final Docker tag 
#
PROJECT = ska-low-mccs

# KUBE_NAMESPACE defines the Kubernetes Namespace that will be deployed to
# using Helm.  If this does not already exist it will be created
KUBE_NAMESPACE ?= mccs

# HELM_RELEASE is the release that all Kubernetes resources will be labelled
# with
RELEASE_NAME ?= test

# HELM_CHART the chart name
HELM_CHART ?= mccs-umbrella

UMBRELLA_CHART_PATH ?= charts/mccs-umbrella/

# INGRESS_HOST is the host name used in the Ingress resource definition for
# publishing services via the Ingress Controller
INGRESS_HOST ?= $(HELM_RELEASE).$(HELM_CHART).local

# Fixed variables
# Timeout for gitlab-runner when run locally
TIMEOUT = 86400
# Helm version
HELM_VERSION = v3.3.1
# kubectl version
KUBERNETES_VERSION = v1.19.2

# minikube needs a Persistent Volume modified to be writable by the tango
# user/group 1000. This will require sudo access in "make create_tmp"
MINIKUBE_TMP = /tmp/minikube-tango

# where to put the output of "make functional-test"
TEST_RESULTS_DIR = testing/results

# Docker, K8s and Gitlab CI variables
# gitlab-runner debug mode - turn on with non-empty value
RDEBUG ?=
# gitlab-runner executor - shell or docker
EXECUTOR ?= shell
# DOCKER_HOST connector to gitlab-runner - local domain socket for shell exec
DOCKER_HOST ?= unix:///var/run/docker.sock
# DOCKER_VOLUMES pass in local domain socket for DOCKER_HOST
DOCKER_VOLUMES ?= /var/run/docker.sock:/var/run/docker.sock
# registry credentials - user/pass/registry - set these in PrivateRules.mak
DOCKER_REGISTRY_USER_LOGIN ?=  ## registry credentials - user - set in PrivateRules.mak
CI_REGISTRY_PASS_LOGIN ?=  ## registry credentials - pass - set in PrivateRules.mak
CI_REGISTRY ?= gitlab.com/ska-telescope/$(PROJECT)
KUBE_CONFIG_BASE64 ?=  ## base64 encoded kubectl credentials for KUBECONFIG
KUBECONFIG ?= /etc/deploy/config ## KUBECONFIG location

VALUES_FILE ?= values-development.yaml
CUSTOM_VALUES = 

ifneq ($(CI_JOB_ID),)
CI_PROJECT_IMAGE := 
VALUES_FILE = values-gitlab-ci.yaml
CUSTOM_VALUES = --set ska-low-mccs.mccs.image.registry=$(CI_REGISTRY)/ska-telescope \
	--set ska-low-mccs.mccs.image.tag=$(CI_COMMIT_SHORT_SHA)
else
endif

ifneq ($(VALUES_FILE),)
CUSTOM_VALUES := --values $(VALUES_FILE) $(CUSTOM_VALUES)
else
endif

XAUTHORITYx ?= ${XAUTHORITY}

IF_COMMAND := ifconfig
ifeq (, $(shell which ifconfig))
	IF_COMMAND := ip a
endif

THIS_HOST := $(shell $(IF_COMMAND) | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p' | head -n1)
DISPLAY := $(THIS_HOST):0

# define private overrides for above variables in here
-include PrivateRules.mak

# Test runner - run to completion job in K8s
TEST_RUNNER = test-runner-$(HELM_CHART)-$(HELM_RELEASE)

#
# include makefile to pick up the standard Make targets, e.g., 'make build'
# build, 'make push' docker push procedure, etc. The other Make targets
# ('make interactive', 'make test', etc.) are defined in this file.
#
include .make/release.mk
include .make/docker.mk
include .make/k8s.mk

.PHONY: all help k8s show deploy delete logs describe mkcerts localip namespace delete-namespace kubeconfig rlint
