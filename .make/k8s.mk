HELM_HOST ?= https://artefact.skao.int## helm host url https
# use values-<deployment>.yaml files instead as --set overrides
#MINIKUBE ?= true## Minikube or not 
MARK ?= all
TANGO_HOST ?= tango-host-databaseds-from-makefile-$(RELEASE_NAME):10000## TANGO_HOST is an input!
LINTING_OUTPUT=$(shell helm lint charts/* | grep ERROR -c | tail -1)
SLEEPTIME ?= 30
MAX_WAIT ?= 180s

EXTERNAL_IP ?= $(shell kubectl config view | gawk 'match($$0, /server: https:\/\/(.*):/, ip) {print ip[1]}')

CHARTS ?= ska-low-mccs mccs-umbrella

CI_PROJECT_PATH_SLUG ?= ska-low-mccs
CI_ENVIRONMENT_SLUG ?= ska-low-mccs

helm_add_stable_repo := helm repo add stable https://charts.helm.sh/stable

k8s: ## Which kubernetes are we connected to
	@echo "Kubernetes cluster-info:"
	@kubectl cluster-info
	@echo ""
	@echo "kubectl version:"
	@kubectl version
	@echo ""
	@echo "Helm version:"
	@helm version --client

namespace: ## create the kubernetes namespace
	@kubectl describe namespace $(KUBE_NAMESPACE) > /dev/null 2>&1 ; \
		K_DESC=$$? ; \
		if [ $$K_DESC -eq 0 ] ; \
			then kubectl describe namespace $(KUBE_NAMESPACE); \
			else kubectl create namespace $(KUBE_NAMESPACE); \
		fi

delete-namespace: ## delete the kubernetes namespace
	@if [ "default" == "$(KUBE_NAMESPACE)" ] || [ "kube-system" == "$(KUBE_NAMESPACE)" ]; then \
	echo "You cannot delete Namespace: $(KUBE_NAMESPACE)"; \
	exit 1; \
	else \
	kubectl describe namespace $(KUBE_NAMESPACE) && kubectl delete namespace $(KUBE_NAMESPACE); \
	fi

package: ## package charts
	@echo "Packaging helm charts. Any existing file won't be overwritten."; \
	mkdir -p ../tmp
	@for i in $(CHARTS); do \
		helm package $${i} --destination ../tmp > /dev/null; \
	done; \
	mkdir -p ../repository && cp -n ../tmp/* ../repository; \
	cd ../repository && helm repo index .; \
	rm -rf ../tmp

clean: ## clean out references to chart tgz's
		@rm -f ./charts/*/charts/*.tgz ./charts/*/Chart.lock ./charts/*/requirements.lock ./repository/*

dep-up: ## update dependencies for every charts in the env var CHARTS
		@cd charts; \
		for i in $(CHARTS); do \
		echo "+++ Updating $${i} chart +++"; \
		helm dependency update $${i}; \
		done;

# minikube only
minikube-setup:
	@test $$(kubectl config current-context | grep minikube) || exit 0; \
	test ! -d $(MINIKUBE_TMP) && mkdir $(MINIKUBE_TMP); \
	owner=$$(stat -c "%u:%g" $(MINIKUBE_TMP) ); \
	if [ $$owner != "1000:1000" ]; \
	then echo "changing permissions of $(MINIKUBE_TMP) to tango user (1000)"; \
	sudo chown 1000:1000 $(MINIKUBE_TMP);fi


install-chart: clean dep-up namespace## install the helm chart with name RELEASE_NAME and path UMBRELLA_CHART_PATH on the namespace KUBE_NAMESPACE
		@sed -e 's/CI_PROJECT_PATH_SLUG/$(CI_PROJECT_PATH_SLUG)/' $(UMBRELLA_CHART_PATH)/values.yaml > generated_values.yaml; \
		sed -e 's/CI_ENVIRONMENT_SLUG/$(CI_ENVIRONMENT_SLUG)/' generated_values.yaml > tmp_values.yaml; \
		helm install $(RELEASE_NAME) \
		--set global.tango_host=$(TANGO_HOST) \
		--set minikubeHostPath=$(MINIKUBE_TMP) \
		--values tmp_values.yaml $(CUSTOM_VALUES) \
		 $(UMBRELLA_CHART_PATH) --namespace $(KUBE_NAMESPACE); \
		 rm generated_values.yaml; \
		 rm tmp_values.yaml

template-chart: clean dep-up namespace## install the helm chart with name RELEASE_NAME and path UMBRELLA_CHART_PATH on the namespace KUBE_NAMESPACE
		@sed -e 's/CI_PROJECT_PATH_SLUG/$(CI_PROJECT_PATH_SLUG)/' $(UMBRELLA_CHART_PATH)/values.yaml > generated_values.yaml; \
		sed -e 's/CI_ENVIRONMENT_SLUG/$(CI_ENVIRONMENT_SLUG)/' generated_values.yaml > tmp_values.yaml; \
		helm template $(RELEASE_NAME) \
		--set global.tango_host=$(TANGO_HOST) \
		--set minikubeHostPath=$(MINIKUBE_TMP) \
		--values tmp_values.yaml $(CUSTOM_VALUES) \
		 $(UMBRELLA_CHART_PATH) --namespace $(KUBE_NAMESPACE); \
		 rm generated_values.yaml; \
		 rm tmp_values.yaml

# chart_lint: dep-up ## lint check the helm chart
lint-chart: dep-up ## lint check the helm chart
	@mkdir -p build; \
	helm lint $(UMBRELLA_CHART_PATH) $(CUSTOM_VALUES); \
	echo "<testsuites><testsuite errors=\"$(LINTING_OUTPUT)\" failures=\"0\" name=\"helm-lint\" skipped=\"0\" tests=\"0\" time=\"0.000\" timestamp=\"$(shell date)\"> </testsuite> </testsuites>" > build/linting.xml
	exit $(LINTING_OUTPUT)

uninstall-chart: ## delete the helm chart release
	@helm uninstall $(RELEASE_NAME) --namespace $(KUBE_NAMESPACE)

reinstall-chart: uninstall-chart install-chart

upgrade-chart: ## upgrade the  helm chart
	@sed -e 's/CI_PROJECT_PATH_SLUG/$(CI_PROJECT_PATH_SLUG)/' $(UMBRELLA_CHART_PATH)values.yaml > generated_values.yaml; \
		sed -e 's/CI_ENVIRONMENT_SLUG/$(CI_ENVIRONMENT_SLUG)/' generated_values.yaml > tmp_values.yaml; \
		helm upgrade $(RELEASE_NAME) \
		--set global.tango_host=$(TANGO_HOST) \
		--set minikubeHostPath=$(MINIKUBE_TMP) \
		--values tmp_values.yaml $(CUSTOM_VALUES) \
		 $(UMBRELLA_CHART_PATH) --namespace $(KUBE_NAMESPACE); \
		 rm generated_values.yaml; \
		 rm tmp_values.yaml


describe: ## describe Pods executed from Helm chart
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -l app.kubernetes.io/instance=$(RELEASE_NAME) -o=name`; \
	do echo "---------------------------------------------------"; \
	echo "Describe for $${i}"; \
	echo kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	echo ""; echo ""; echo ""; \
	done

logs: ## show Helm chart POD logs
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -o=name -l 'domain=$(PROJECT)'`; \
	do \
	echo "---------------------------------------------------"; \
	echo "Logs for $${i}"; \
	echo kubectl logs -n $(KUBE_NAMESPACE) $${i}; \
	echo "---------------------------------------------------"; \
	kubectl logs -n $(KUBE_NAMESPACE) $${i}; \
	echo "---------------------------------------------------"; \
	echo ""; \
	done

tail:  ## provide pod=pod-name
	@if [ -z "$$pod" ]; \
	then echo "usage:";echo "  make tail pod=<pod-name>"; \
	echo "deviceserver pods are: ";` echo kubectl -n $(KUBE_NAMESPACE) get pod -o name -l 'domain=$(PROJECT)'`;exit 0; fi; \
	echo "kubectl -n $(KUBE_NAMESPACE) logs -f  $${pod};" && \
	kubectl -n $(KUBE_NAMESPACE) logs -f $${pod};

kubeconfig: ## export current KUBECONFIG as base64 ready for KUBE_CONFIG_BASE64
	@KUBE_CONFIG_BASE64=`kubectl config view --flatten | base64 -w 0`; \
	echo "KUBE_CONFIG_BASE64: $$(echo $${KUBE_CONFIG_BASE64} | cut -c 1-40)..."; \
	echo "appended to: PrivateRules.mak"; \
	echo -e "\n\n# base64 encoded from: kubectl config view --flatten\nKUBE_CONFIG_BASE64 = $${KUBE_CONFIG_BASE64}" >> PrivateRules.mak

# run helm  test 
functional-test helm-test test: ## test the application on K8s
	@helm test $(RELEASE_NAME) --namespace $(KUBE_NAMESPACE); \
	test_retcode=$$?; \
	yaml=$$(mktemp --suffix=.yaml); \
	sed -e "s/\(claimName:\).*/\1 teststore-$(HELM_CHART)-$(RELEASE_NAME)/" charts/test-fetcher.yaml >> $$yaml; \
	kubectl apply -n $(KUBE_NAMESPACE) -f $$yaml; \
	kubectl -n $(KUBE_NAMESPACE) wait --for=condition=ready --timeout=${MAX_WAIT} -f $$yaml; \
	rm -rf $(TEST_RESULTS_DIR); mkdir $(TEST_RESULTS_DIR); \
	kubectl -n $(KUBE_NAMESPACE) cp test-fetcher:/results $(TEST_RESULTS_DIR); \
	python3 .wait_for_report_file.py; \
	report_retcode=$$?; \
	echo "test report:"; \
	cat $(TEST_RESULTS_DIR)/*; echo; \
	kubectl -n $(KUBE_NAMESPACE) delete pod -l transient; \
	kubectl -n $(KUBE_NAMESPACE) delete -f $$yaml --now; rm $$yaml; \
	exit $$test_retcode || $$report_retcode

wait:
	@echo "Waiting for device servers to be ready"
	@date
	@kubectl -n $(KUBE_NAMESPACE) get pods
	@jobs=$$(kubectl get job --output=jsonpath={.items..metadata.name} -n $(KUBE_NAMESPACE)); \
	kubectl -n $(KUBE_NAMESPACE) wait job --for=condition=complete --timeout=${MAX_WAIT} $$jobs 
	@kubectl -n $(KUBE_NAMESPACE) wait --for=condition=ready --timeout=${MAX_WAIT} -l 'app=$(PROJECT)' pods || exit 1
	@date

bounce:
	@echo "stopping ..."; \
	kubectl -n $(KUBE_NAMESPACE) scale --replicas=0 statefulset.apps -l 'domain=$(PROJECT)'; \
	echo "starting ..."; \
	kubectl -n $(KUBE_NAMESPACE) scale --replicas=1 statefulset.apps -l 'domain=$(PROJECT)'; \
	echo "WARN: 'make wait' for terminating pods not possible. Use 'make watch'"

help:  ## show this help.
	@echo "make targets:"
	@grep -hE '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo ""; echo "make vars (+defaults):"
	@grep -hE '^[0-9a-zA-Z_-]+ \?=.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = " ?= "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\#\#/  \#/'

smoketest: ## check that the number of waiting containers is zero (10 attempts, wait time 30s).
	@echo "Smoke test START"; \
	n=10; \
	while [ $$n -gt 0 ]; do \
			waiting=`kubectl get pods -n $(KUBE_NAMESPACE) -o=jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | wc -w`; \
			echo "Waiting containers=$$waiting"; \
			if [ $$waiting -ne 0 ]; then \
					echo "Waiting $(SLEEPTIME) for pods to become running...#$$n"; \
					sleep $(SLEEPTIME); \
			fi; \
			if [ $$waiting -eq 0 ]; then \
					echo "Smoke test SUCCESS"; \
					exit 0; \
			fi; \
			if [ $$n -eq 1 ]; then \
					waiting=`kubectl get pods -n $(KUBE_NAMESPACE) -o=jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}' | wc -w`; \
					echo "Smoke test FAILS"; \
					echo "Found $$waiting waiting containers: "; \
					kubectl get pods -n $(KUBE_NAMESPACE) -o=jsonpath='{range .items[*].status.containerStatuses[?(.state.waiting)]}{.state.waiting.message}{"\n"}{end}'; \
					exit 1; \
			fi; \
			n=`expr $$n - 1`; \
	done

itango:
	kubectl exec -it -n $(KUBE_NAMESPACE) ska-tango-base-itango-console  -- itango3

cli:
	kubectl exec -it -n $(KUBE_NAMESPACE)  mccs-mccs-cli -- bash

watch:
	watch kubectl get all,pv,pvc,ingress -n $(KUBE_NAMESPACE)

