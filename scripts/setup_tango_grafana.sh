#!/bin/bash
# This does assume k8s is using a docker driver
# Not in the VSCode container!
#
git clone https://gitlab.com/ska-telescope/TANGO-grafana.git
git clone https://gitlab.com/ska-telescope/skampi.git
cd skampi
make deploy HELM_CHART=tango-base

if [ $(kubectl get all -n kube-system | grep -c traefik) != 4 ];then
        make traefik EXTERNAL_IP=$(kubectl config view | gawk 'match($0, /server: https:\/\/(.*):/, ip) {print ip[1]}')
fi
cd ../TANGO-grafana
git submodule update --init --recursive
make install-chart
cd ../..
echo
echo 1 of 2: Waiting for all pods to be created and ready to use
kubectl wait --all-namespaces --for=condition=ready --timeout=800s --all pods

# Create an ska-low-mccs:latest docker image reflecting the repository
make devimage
# Set environment variable to prevent tango-base being deployed again
export TANGO_BASE_ENABLED=false
# Starts up mccs
make deploy

# Install the skampi archiver
cd scripts/skampi
git apply ../skampi.patch
make deploy HELM_CHART=archiver
echo
echo 2 of 2: Waiting for all pods to be created and ready to use
kubectl wait -n integration --for=condition=complete --timeout=120s job.batch/attrconfig-archiver-test
