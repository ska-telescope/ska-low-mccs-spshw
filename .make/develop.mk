ifneq ($(REBUILD_TOX),)
REBUILD_ARG := -r
endif

UID := $(shell id -u)
GID := $(shell id -g)

develop:
	@docker build --build-arg UID=${UID} --build-arg GID=${GID} \
	-t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -ti -v $(PWD):/app \
	ska_low_mccs_tester bash

tests:
	@docker build --build-arg UID=${UID} --build-arg GID=${GID} \
	-t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -v $(PWD):/app \
	ska_low_mccs_tester tox ${REBUILD_ARG} -e py

lint:
	@docker build --build-arg UID=${UID} --build-arg GID=${GID} \
	-t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -v $(PWD):/app \
	ska_low_mccs_tester tox ${REBUILD_ARG} -e lint

docs:
	@docker build -t ska_low_mccs_docs_builder  . -f docs/Dockerfile
	@docker run --rm -v $(PWD):/project --user ${UID}:${GID} ska_low_mccs_docs_builder

testdocs:
	@docker build -t ska_low_mccs_testdocs_builder --build-arg dir=testing/docs . -f docs/Dockerfile 
	@docker run --rm -v $(PWD):/project --user ${UID}:${GID} ska_low_mccs_testdocs_builder
