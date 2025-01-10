#
# Project makefile for a SKA LOW MCCS SPSHW project.
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
#
PROJECT = ska-low-mccs-spshw
include .make/base.mk

########################################################################
# DOCS
########################################################################
include .make/docs.mk

DOCS_SPHINXOPTS = -W --keep-going

docs-pre-build:
	poetry config virtualenvs.create false
	poetry install --no-root --only docs

.PHONY: docs-pre-build

########################################################################
# PYTHON
########################################################################
include .make/python.mk

PYTHON_LINE_LENGTH = 88
PYTHON_LINT_TARGET = src tests  ## Paths containing python to be formatted and linted
PYTHON_VARS_AFTER_PYTEST = --forked
PYTHON_TEST_FILE = tests

python-post-lint:
	mypy --config-file mypy.ini src/ tests

.PHONY: python-post-lint


########################################################################
# OCI
########################################################################
include .make/oci.mk

FIRMWARE_VERSION = 6.0.0
DESIRED_FIRMWARE_FILE_NAME = itpm_v1_6.bit

install-firmware:
	mkdir temp_firmware
	curl -sSL --retry 3 --connect-timeout 15 --output temp_firmware/firmware_files.tar.gz https://artefact.skao.int/repository/raw-internal/ska_low_sps_tpmfirmware-$(FIRMWARE_VERSION).tar.gz
	gzip -d temp_firmware/firmware_files.tar.gz
	tar -xvf temp_firmware/firmware_files.tar -C temp_firmware
	cp temp_firmware/tpm_firmware.bit $(DESIRED_FIRMWARE_FILE_NAME)
	rm -rf temp_firmware

########################################################################
# HELM
########################################################################
include .make/helm.mk

HELM_CHARTS_TO_PUBLISH = ska-low-mccs-spshw

helm-pre-build:
	helm repo add skao https://artefact.skao.int/repository/helm-internal
	helm repo add bitnami https://charts.bitnami.com/bitnami


########################################################################
# K8S
########################################################################
K8S_USE_HELMFILE = true
K8S_HELMFILE = helmfile.d/helmfile.yaml

ifdef CI_COMMIT_SHORT_SHA
K8S_HELMFILE_ENV ?= stfc-ci
else
K8S_HELMFILE_ENV ?= minikube-ci
endif

include .make/k8s.mk
include .make/raw.mk
include .make/xray.mk

ifdef CI_REGISTRY_IMAGE
K8S_CHART_PARAMS += \
	--selector chart=ska-low-mccs-spshw \
	--selector chart=ska-tango-base \
	--set image.registry=$(CI_REGISTRY_IMAGE) \
	--set image.tag=$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA) \
	--set global.exposeAllDS=false
endif

JUNITXML_REPORT_PATH ?= build/reports/functional-tests.xml
CUCUMBER_JSON_PATH ?= build/reports/cucumber.json
JSON_REPORT_PATH ?= build/reports/report.json

K8S_TEST_RUNNER_PYTEST_OPTIONS = -v --true-context \
	--junitxml=$(JUNITXML_REPORT_PATH) \
	--cucumberjson=$(CUCUMBER_JSON_PATH) \
	--json-report --json-report-file=$(JSON_REPORT_PATH)

ifdef HW_DEPLOYMENT
K8S_TEST_RUNNER_PYTEST_OPTIONS += --hw-deployment
endif

K8S_TEST_RUNNER_PYTEST_TARGET = tests/functional
K8S_TEST_RUNNER_PIP_INSTALL_ARGS = -r tests/functional/requirements.txt

K8S_TEST_RUNNER_CHART_REGISTRY ?= https://artefact.skao.int/repository/helm-internal
K8S_TEST_RUNNER_CHART_NAME ?= ska-low-mccs-k8s-test-runner
K8S_TEST_RUNNER_CHART_TAG ?= 0.9.1

K8S_TEST_RUNNER_VOLUME_TO_MOUNT=daq-data

K8S_TEST_RUNNER_CHART_OVERRIDES = --set global.tango_host=databaseds-tango-base:10000  # TODO: This should be the default in the k8s-test-runner

ifdef PASS_PROXY_CONFIG
FACILITY_HTTP_PROXY ?= $(http_proxy)
FACILITY_HTTPS_PROXY ?= $(https_proxy)
endif

ifdef FACILITY_HTTP_PROXY
K8S_TEST_RUNNER_CHART_OVERRIDES += --set global.http_proxy=$(FACILITY_HTTP_PROXY)
endif

ifdef FACILITY_HTTPS_PROXY
K8S_TEST_RUNNER_CHART_OVERRIDES += --set global.https_proxy=$(FACILITY_HTTPS_PROXY)
endif

ifdef K8S_TEST_RUNNER_VOLUME_TO_MOUNT
K8S_TEST_RUNNER_CHART_OVERRIDES += --set storage.volume_to_mount=$(K8S_TEST_RUNNER_VOLUME_TO_MOUNT)
endif

ifdef K8S_TEST_RUNNER_IMAGE_REGISTRY
K8S_TEST_RUNNER_CHART_OVERRIDES += --set image.registry=$(K8S_TEST_RUNNER_IMAGE_REGISTRY)
endif

ifdef K8S_TEST_RUNNER_IMAGE_NAME
K8S_TEST_RUNNER_CHART_OVERRIDES += --set image.image=$(K8S_TEST_RUNNER_IMAGE_NAME)
endif

ifdef K8S_TEST_RUNNER_IMAGE_TAG
K8S_TEST_RUNNER_CHART_OVERRIDES += --set image.tag=$(K8S_TEST_RUNNER_IMAGE_TAG)
endif

ifdef CI_COMMIT_SHORT_SHA
K8S_TEST_RUNNER_CHART_RELEASE = k8s-test-runner-$(CI_COMMIT_SHORT_SHA)
else
K8S_TEST_RUNNER_CHART_RELEASE = k8s-test-runner
endif

K8S_TEST_RUNNER_PIP_INSTALL_COMMAND =
ifdef K8S_TEST_RUNNER_PIP_INSTALL_ARGS
K8S_TEST_RUNNER_PIP_INSTALL_COMMAND = pip install ${K8S_TEST_RUNNER_PIP_INSTALL_ARGS}
endif

K8S_TEST_RUNNER_WORKING_DIRECTORY ?= /home/tango

k8s-do-test:
	helm -n $(KUBE_NAMESPACE) upgrade --install --repo $(K8S_TEST_RUNNER_CHART_REGISTRY) \
		$(K8S_TEST_RUNNER_CHART_RELEASE) $(K8S_TEST_RUNNER_CHART_NAME) \
		--version $(K8S_TEST_RUNNER_CHART_TAG) $(K8S_TEST_RUNNER_CHART_OVERRIDES)
	kubectl -n $(KUBE_NAMESPACE) wait pod ska-low-mccs-k8s-test-runner \
		--for=condition=ready --timeout=$(K8S_TIMEOUT)
	kubectl -n $(KUBE_NAMESPACE) cp tests/ ska-low-mccs-k8s-test-runner:$(K8S_TEST_RUNNER_WORKING_DIRECTORY)/tests
	kubectl -n $(KUBE_NAMESPACE) exec ska-low-mccs-k8s-test-runner -- bash -c \
		"cd $(K8S_TEST_RUNNER_WORKING_DIRECTORY) && \
		mkdir -p build/reports && \
		$(K8S_TEST_RUNNER_PIP_INSTALL_COMMAND) && \
		STATION_LABEL=$(STATION_LABEL) pytest $(K8S_TEST_RUNNER_PYTEST_OPTIONS) $(K8S_TEST_RUNNER_PYTEST_TARGET)" ; \
	EXIT_CODE=$$? ; \
	kubectl -n $(KUBE_NAMESPACE) cp ska-low-mccs-k8s-test-runner:$(K8S_TEST_RUNNER_WORKING_DIRECTORY)/build/ ./build/ ; \
	helm  -n $(KUBE_NAMESPACE) uninstall $(K8S_TEST_RUNNER_CHART_RELEASE) ; \
	echo $$EXIT_CODE > build/status
	exit $$EXIT_CODE

telmodel-deps:
	pip install --extra-index-url https://artefact.skao.int/repository/pypi-internal/simple ska-telmodel check-jsonschema

k8s-pre-install-chart: telmodel-deps
k8s-pre-uninstall-chart: telmodel-deps

.PHONY: k8s-do-test


########################################################################
# HELMFILE
########################################################################
helmfile-lint: telmodel-deps
	SKIPDEPS=""
	for environment in minikube-ci stfc-ci aa0.5-production arcetri gmrt low-itf low-itf-minikube oxford psi-low psi-low-minikube ral-software ral-software-minikube ; do \
        echo "Linting helmfile against environment '$$environment'" ; \
		helmfile -e $$environment lint $$SKIPDEPS; \
		EXIT_CODE=$$? ; \
		if [ $$EXIT_CODE -gt 0 ]; then \
		echo "Linting of helmfile against environment '$$environment' FAILED." ; \
		break ; \
		fi ; \
		SKIPDEPS="--skip-deps" ; \
	done ; \
	exit $$EXIT_CODE

.PHONY: helmfile-lint telmodel-deps



########################################################################
# PRIVATE OVERRIDES
########################################################################

-include PrivateRules.mak
