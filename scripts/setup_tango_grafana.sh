#!/bin/bash
# This does assume k8s is using a docker driver
# Not in the VSCode container!
#
git clone https://gitlab.com/ska-telescope/TANGO-grafana.git
make install-traefik
cd ../TANGO-grafana
git submodule update --init --recursive
make install-chart
cd ../..
echo
echo 1 of 3: Waiting for all pods to be created and ready to use
kubectl wait --all-namespaces --for=condition=ready --timeout=800s --all pods

# Create an ska-low-mccs:latest docker image reflecting the repository
make devimage

# Starts up mccs
make install-chart
echo
echo 2 of 3: Waiting for all pods to be created and ready to use
kubectl wait -n integration --for=condition=ready --timeout=300s --all pods

# Install the skampi archiver
cd scripts
cp attribute2archive.json skampi/charts/skampi/charts/archiver/data/
cd skampi
make deploy HELM_CHART=archiver VALUES=../enable_archiver.yaml
echo
echo 3 of 3: Waiting for all pods to be created and ready to use
kubectl wait -n integration --for=condition=complete --timeout=120s job.batch/attrconfig-archiver-test
