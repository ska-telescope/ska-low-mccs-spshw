#!/bin/bash
# From a very clean start (No minikube running)
# This does assume k8s is using a docker driver
# Not in the VSCode container!
# Open standard terminal window (Don't reuse a previous one!!!)
#
minikube start
git clone https://gitlab.com/ska-telescope/skampi.git
cd skampi
make deploy HELM_CHART=tango-base
make deploy HELM_CHART=webjive
cd ..
watch -n 5 kubectl get pods --all-namespaces # Wait for STATUS=Running for all pods
