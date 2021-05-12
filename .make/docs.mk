
docs:
	@docker build -t ska_low_mccs_docs_builder  . -f docs/Dockerfile
	@docker run --rm -v $(PWD):/project --user $(id -u):$(id -g) ska_low_mccs_docs_builder

testdocs:
	@docker build -t ska_low_mccs_testdocs_builder --build-arg dir=testing/docs . -f docs/Dockerfile 
	@docker run --rm -v $(PWD):/project --user $(id -u):$(id -g) ska_low_mccs_testdocs_builder
