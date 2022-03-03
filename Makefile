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

#PYTHON_RUNNER = poetry run

# E203 and W503 conflict with black
PYTHON_SWITCHES_FOR_FLAKE8 = --extend-ignore=BLK,T --enable=DAR104 --ignore=E203,FS003,W503,N802,E231,RST303 --max-complexity=10 \
    --docstring-style=SPHINX  --max-line-length=110 --rst-roles=py:attr,py:class,py:const,py:exc,py:func,py:meth,py:mod
PYTHON_SWITCHES_FOR_BLACK = --line-length=110
PYTHON_SWITCHES_FOR_ISORT = --skip-glob=*/__init__.py -w=110
PYTHON_TEST_FILE = testing/src/
PYTHON_LINT_TARGET = src/ska_low_mccs testing/src/tests  ## Paths containing python to be formatted and linted
# Disable warning, convention, and refactoring messages
# Disable errors E1101 (no-member), E1136 (unsubscriptable-object), E0611 (no-name-in-module), E0603 (undefined-all-variable),
# E1121 (too-many-function-args), E1120 (no-value-for-parameter)
PYTHON_SWITCHES_FOR_PYLINT = --disable=W,C,R,E1101,E1136,E0611,E0603,E1121,E1120 # too-many-function-args,no-value-for-parameter \
    #--ignored-modules=astropy.constants,numpy --extension-pkg-whitelist=astropy.constants \
    #--generated-members=requests.codes.ok
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
python-post-format:
	$(PYTHON_RUNNER) docformatter -r -i --wrap-summaries 88 --wrap-descriptions 72 --pre-summary-newline src/ testing/src/ 	

python-post-lint:
	$(PYTHON_RUNNER) mypy --config-file mypy.ini src/ testing/src/

.PHONY: python-post-format python-post-lint
