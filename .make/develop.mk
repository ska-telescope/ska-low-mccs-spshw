ifneq ($(REBUILD_TOX),)
REBUILD_ARG := -r
endif

develop:
	@docker build -t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -ti -v $(PWD):/app \
	--user $(id -u):$(id -g) \
	--env TOX_WORK_DIR=.tox.make \
	ska_low_mccs_tester bash

tests:
	@docker build -t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -v $(PWD):/app \
	--user $(id -u):$(id -g) \
	--env TOX_WORK_DIR=.tox.make \
	ska_low_mccs_tester tox ${REBUILD_ARG} -e py

lint:
	@docker build -t ska_low_mccs_tester . -f develop.Dockerfile
	@docker run --rm -v $(PWD):/app \
	--user $(id -u):$(id -g) \
	--env TOX_WORK_DIR=.tox.make \
	ska_low_mccs_tester tox ${REBUILD_ARG} -e lint

docs:
	@docker build -t ska_low_mccs_docs_builder  . -f docs/Dockerfile
	@docker run --rm -v $(PWD):/project --user $(id -u):$(id -g) ska_low_mccs_docs_builder

testdocs:
	@docker build -t ska_low_mccs_testdocs_builder --build-arg dir=testing/docs . -f docs/Dockerfile 
	@docker run --rm -v $(PWD):/project --user $(id -u):$(id -g) ska_low_mccs_testdocs_builder
