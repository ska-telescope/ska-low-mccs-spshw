#
# Project makefile for a SKA LOW MCCS project. 
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
#
PROJECT = ska-low-mccs

HELM_CHARTS_TO_PUBLISH = ska-low-mccs

PYTHON_SWITCHES_FOR_BLACK = --line-length=88
PYTHON_SWITCHES_FOR_ISORT = --skip-glob=*/__init__.py -w=88
PYTHON_LINT_TARGET = src/ska_low_mccs tests  ## Paths containing python to be formatted and linted
PYTHON_VARS_AFTER_PYTEST = --forked
PYTHON_TEST_FILE = tests
K8S_TESTBED ?= test
DOCS_SPHINXOPTS = -n -W --keep-going

include .make/oci.mk
include .make/k8s.mk
include .make/python.mk
include .make/raw.mk
include .make/base.mk
include .make/docs.mk
include .make/helm.mk

# define private overrides for above variables in here
-include PrivateRules.mak

#ifneq ($(strip $(CI_JOB_ID)),)
ifneq ($(CI_REGISTRY),)
K8S_CHART_PARAMS = --set low_mccs.image.tag=$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA) \
	--set low_mccs.image.registry=$(CI_REGISTRY_IMAGE)
K8S_TEST_IMAGE_TO_TEST = $(CI_REGISTRY_IMAGE)/$(NAME):$(VERSION)-dev.c$(CI_COMMIT_SHORT_SHA)
else
K8S_TEST_IMAGE_TO_TEST = $(CAR_OCI_REGISTRY_HOST)/$(NAME):$(VERSION)
endif

ifeq ($(MAKECMDGOALS),k8s-test)
PYTHON_VARS_AFTER_PYTEST += --testbed $(K8S_TESTBED)
PYTHON_TEST_FILE = tests/functional
else
PYTHON_VARS_AFTER_PYTEST +=  --cov-fail-under=10
endif

K8S_TEST_TEST_COMMAND = $(PYTHON_VARS_BEFORE_PYTEST) $(PYTHON_RUNNER) \
						pytest \
						$(PYTHON_VARS_AFTER_PYTEST) ./tests/functional \
						 | tee pytest.stdout

python-post-format:
	$(PYTHON_RUNNER) docformatter -r -i --wrap-summaries 88 --wrap-descriptions 72 --pre-summary-newline src/ tests/ 	

# Add this for typehints & static type checking
python-post-lint:
	$(PYTHON_RUNNER) mypy --config-file mypy.ini src/ tests

.PHONY: python-post-format python-post-lint
