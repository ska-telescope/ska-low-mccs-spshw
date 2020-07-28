#!/bin/bash
# This does assume k8s is using a docker driver
# Not in the VSCode container!
# Open standard terminal window (Don't reuse a previous one!!!)
#
git clone https://gitlab.com/ska-telescope/skampi.git
cd skampi
make deploy HELM_CHART=tango-base
make deploy HELM_CHART=webjive
echo
echo Waiting for all pods to be created and ready to use
kubectl -n integration wait --for=condition=ready --timeout=600s --all pods
