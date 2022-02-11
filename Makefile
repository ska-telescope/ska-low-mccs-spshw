#
# Project makefile for a Tango project. You should normally only need to modify
# DOCKER_REGISTRY_USER and PROJECT below.
#

#
# DOCKER_REGISTRY_HOST, DOCKER_REGISTRY_USER and PROJECT are combined to define
# the Docker tag for this project. The definition below inherits the standard
# value for DOCKER_REGISTRY_HOST (=rartefact.skao.int) and overwrites
# DOCKER_REGISTRY_USER and PROJECT to give a final Docker tag 
#
PROJECT = ska-low-mccs

# E203 and W503 conflict with black
PYTHON_SWITCHES_FOR_FLAKE8 = --extend-ignore=BLK,T --enable=DAR104 --ignore=E203,FS003,W503,N802,E231,RST303 --max-complexity=10 \
    --docstring-style=SPHINX  --max-line-length=110 --rst-roles=py:attr,py:class,py:const,py:exc,py:func,py:meth,py:mod
PYTHON_SWITCHES_FOR_BLACK = --line-length=110
PYTHON_SWITCHES_FOR_ISORT = --skip-glob=*/__init__.py -w=110
PYTHON_TEST_FILE = testing/src/
PYTHON_LINT_TARGET = src/ska_low_mccs testing/src/tests  ## Paths containing python to be formatted and linted
PYTHON_SWITCHES_FOR_PYLINT = --disable=W,C,R --ignored-modules=astropy.constants --extension-pkg-whitelist=astropy.constants
DOCS_SOURCEDIR=./docs/source


include .make/oci.mk
include .make/k8s.mk
include .make/helm.mk
include .make/python.mk
include .make/raw.mk
include .make/base.mk

# define private overrides for above variables in here
-include PrivateRules.mak

# Add this for typehints & static type checking
python-post-lint:
	$(PYTHON_RUNNER) docformatter -r -i --wrap-summaries 88 --wrap-descriptions 72 --pre-summary-newline src/ testing/src/ 	
	$(PYTHON_RUNNER) mypy --config-file mypy.ini src/ testing/src/
.PHONY: python-post-lint