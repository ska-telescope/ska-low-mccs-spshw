
k8s: ## Which kubernetes are we connected to
	@echo "Kubernetes cluster-info:"
	@kubectl cluster-info
	@echo ""
	@echo "kubectl version:"
	@kubectl version
	@echo ""
	@echo "Helm version:"
	@helm version --client

watch:
	watch kubectl get all,pv,pvc,ingress -n $(KUBE_NAMESPACE)

namespace: ## create the kubernetes namespace
	kubectl describe namespace $(KUBE_NAMESPACE) || kubectl create namespace $(KUBE_NAMESPACE)

delete_namespace: ## delete the kubernetes namespace
	@if [ "default" == "$(KUBE_NAMESPACE)" ] || [ "kube-system" == "$(KUBE_NAMESPACE)" ]; then \
	echo "You cannot delete Namespace: $(KUBE_NAMESPACE)"; \
	exit 1; \
	else \
	kubectl describe namespace $(KUBE_NAMESPACE) && kubectl delete namespace $(KUBE_NAMESPACE); \
	fi

# minikube only 
minikube_setup:
	@test $$(kubectl config current-context | grep minikube) || exit 0; \
	test ! -d $(MINIKUBE_TMP) && mkdir $(MINIKUBE_TMP); \
	owner=$$(stat -c "%u:%g" $(MINIKUBE_TMP) ); \
	if [ $$owner != "1000:1000" ]; \
	then echo "changing permissions of $(MINIKUBE_TMP) to tango user (1000)"; \
	sudo chown 1000:1000 $(MINIKUBE_TMP);fi

deploy: minikube_setup namespace mkcerts depends  ## deploy the helm chart
	@helm install $(HELM_RELEASE) charts/$(HELM_CHART)/ \
		--namespace $(KUBE_NAMESPACE) \
		--set ingress.hostname=$(INGRESS_HOST) \
		--set minikubeHostPath=$(MINIKUBE_TMP) $(CUSTOM_VALUES) 

show: mkcerts ## show the helm chart
	@helm template $(HELM_RELEASE) charts/$(HELM_CHART)/ \
		--namespace $(KUBE_NAMESPACE) \
		--set ingress.hostname=$(INGRESS_HOST) \
		--set minikubeHostPath=$(MINIKUBE_TMP) $(CUSTOM_VALUES)

chart_lint: ## lint check the helm chart
	@helm lint charts/$(HELM_CHART)/ \
		--namespace $(KUBE_NAMESPACE) \
		--set ingress.hostname=$(INGRESS_HOST) \
		$(CUSTOM_VALUES)

delete: ## delete the helm chart release
	@helm uninstall $(HELM_RELEASE) --namespace $(KUBE_NAMESPACE)

describe: ## describe Pods executed from Helm chart
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -l app.kubernetes.io/instance=$(HELM_RELEASE) -o=name`; \
	do echo "---------------------------------------------------"; \
	echo "Describe for $${i}"; \
	echo kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	kubectl -n $(KUBE_NAMESPACE) describe $${i}; \
	echo "---------------------------------------------------"; \
	echo ""; echo ""; echo ""; \
	done

logs: ## show Helm chart POD logs
	@for i in `kubectl -n $(KUBE_NAMESPACE) get pods -o=name -l deviceServer`; \
	do \
	echo "---------------------------------------------------"; \
	echo "Logs for $${i}"; \
	echo kubectl logs -n $(KUBE_NAMESPACE) $${i}; \
	echo "---------------------------------------------------"; \
	kubectl logs -n $(KUBE_NAMESPACE) $${i}; \
	echo "---------------------------------------------------"; \
	echo ""; \
	done

tail:  ## provide alias=name
	@POD=`kubectl -n $(KUBE_NAMESPACE) get pods -o=name -l deviceServer`;\
	if [ -z "$$alias" ]; \
	then echo "usage:";echo "  make tail alias=<name>"; \
	echo "aliases: "`kubectl -n $(KUBE_NAMESPACE) get pod -o jsonpath='{.items[*].metadata.labels.deviceServer}'`;exit 0; fi; \
	echo "kubectl -n $(KUBE_NAMESPACE) logs -f -l deviceServer=$${alias};" && \
	kubectl -n $(KUBE_NAMESPACE) logs -f -l deviceServer=$${alias};

localip:  ## set local Minikube IP in /etc/hosts file for Ingress $(INGRESS_HOST)
	@new_ip=`minikube ip` && \
	existing_ip=`grep $(INGRESS_HOST) /etc/hosts || true` && \
	echo "New IP is: $${new_ip}" && \
	echo "Existing IP: $${existing_ip}" && \
	if [ -z "$${existing_ip}" ]; then echo "$${new_ip} $(INGRESS_HOST)" | sudo tee -a /etc/hosts; \
	else sudo perl -i -ne "s/\d+\.\d+.\d+\.\d+/$${new_ip}/ if /$(INGRESS_HOST)/; print" /etc/hosts; fi && \
	echo "/etc/hosts is now: " `grep $(INGRESS_HOST) /etc/hosts`

mkcerts:  ## Make dummy certificates for $(INGRESS_HOST) and Ingress
	@if [ ! -f charts/$(HELM_CHART)/secrets/tls.key ]; then \
	openssl req -x509 -sha256 -nodes -days 365 -newkey rsa:2048 \
	   -keyout charts/$(HELM_CHART)/secrets/tls.key \
		 -out charts/$(HELM_CHART)/secrets/tls.crt \
		 -subj "/CN=$(INGRESS_HOST)/O=Minikube"; \
	else \
	echo "SSL cert already exists in charts/$(HELM_CHART)/secrets ... skipping"; \
	fi

kubeconfig: ## export current KUBECONFIG as base64 ready for KUBE_CONFIG_BASE64
	@KUBE_CONFIG_BASE64=`kubectl config view --flatten | base64 -w 0`; \
	echo "KUBE_CONFIG_BASE64: $$(echo $${KUBE_CONFIG_BASE64} | cut -c 1-40)..."; \
	echo "appended to: PrivateRules.mak"; \
	echo -e "\n\n# base64 encoded from: kubectl config view --flatten\nKUBE_CONFIG_BASE64 = $${KUBE_CONFIG_BASE64}" >> PrivateRules.mak

# run helm  test 
functional_test: ## test the application on K8s
	@helm test $(HELM_RELEASE) --namespace $(KUBE_NAMESPACE); \
	retcode=$$?; \
	test -n $(RDEBUG) && kubectl -n $(KUBE_NAMESPACE) describe pod functional-$(HELM_CHART)-$(HELM_RELEASE); \
	yaml=$$(mktemp --suffix=.yaml); \
	sed -e "s/\(claimName:\).*/\1 teststore-$(HELM_CHART)-$(HELM_RELEASE)/" charts/test-fetcher.yaml >> $$yaml; \
	kubectl apply -n $(KUBE_NAMESPACE) -f $$yaml; \
	kubectl -n $(KUBE_NAMESPACE) wait --for=condition=ready --timeout=30s -f $$yaml >/dev/null; \
	mkdir -p $(TEST_RESULTS_DIR); kubectl -n $(KUBE_NAMESPACE) cp test-fetcher:/results $(TEST_RESULTS_DIR) > /dev/null; \
	kubectl -n $(KUBE_NAMESPACE) delete pod -l transient > /dev/null; \
	kubectl -n $(KUBE_NAMESPACE) delete -f $$yaml --now; rm $$yaml; \
	echo "test report:"; \
	cat $(TEST_RESULTS_DIR)/*; echo; exit $$retcode

wait:
	@echo "Waiting for device servers to be ready"
	@date
	@kubectl -n $(KUBE_NAMESPACE) get pods -l deviceServer
	@jobs=$$(kubectl get job --output=jsonpath={.items..metadata.name} -n $(KUBE_NAMESPACE)); kubectl wait job --for=condition=complete --timeout=120s $$jobs -n $(KUBE_NAMESPACE)
	@kubectl -n $(KUBE_NAMESPACE) wait --for=condition=ready --timeout=120s -l deviceServer pods || exit 1
	@date

bounce:
	@chart_version=$$(helm -n $(KUBE_NAMESPACE) show chart charts/$(HELM_CHART) |grep version|tail -n 1| awk '{print $$NF;}'); \
	echo "stopping ..."; \
	kubectl -n $(KUBE_NAMESPACE) scale --replicas=0 statefulset.apps -l chart=$(HELM_CHART)-$$chart_version; \
	echo "starting ..."; \
	kubectl -n $(KUBE_NAMESPACE) scale --replicas=1 statefulset.apps -l chart=$(HELM_CHART)-$$chart_version; \
	echo "WARN: 'make wait' for terminating pods not possible. Use 'make watch'"

help:  ## show this help.
	@echo "make targets:"
	@grep -hE '^[0-9a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo ""; echo "make vars (+defaults):"
	@grep -hE '^[0-9a-zA-Z_-]+ \?=.*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = " ?= "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\#\#/  \#/'

smoketest:
	@echo "Smoke test START"

itango:
	kubectl exec -it -n $(KUBE_NAMESPACE) itango-tango-base-$(HELM_RELEASE)  -- itango3

cli:
	kubectl exec -it -n $(KUBE_NAMESPACE) cli-$(HELM_CHART)-$(HELM_RELEASE)  -- bash

depends:
	helm dependency update charts/$(HELM_CHART)/ 
