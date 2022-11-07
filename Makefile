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
PYTHON_TEST_FILE = tests
PYTHON_VARS_AFTER_PYTEST = --cov-fail-under=80
PYTHON_LINT_TARGET = src/ska_low_mccs tests  ## Paths containing python to be formatted and linted

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

python-post-format:
	$(PYTHON_RUNNER) docformatter -r -i --wrap-summaries 88 --wrap-descriptions 72 --pre-summary-newline src/ tests/ 	

# Add this for typehints & static type checking
# removed temporarily
# python-post-lint:
#	$(PYTHON_RUNNER) mypy --config-file mypy.ini src/ tests/

.PHONY: python-post-format python-post-lint
