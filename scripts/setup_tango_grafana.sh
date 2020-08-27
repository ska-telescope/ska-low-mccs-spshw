#!/bin/bash
# This does assume k8s is using a docker driver
# Not in the VSCode container!
#
git clone https://gitlab.com/ska-telescope/TANGO-grafana.git
git clone https://gitlab.com/ska-telescope/skampi.git
cd skampi
make deploy HELM_CHART=tango-base
echo
if [ $(kubectl get all -n kube-system | grep -c traefik) != 4 ];then
        make traefik EXTERNAL_IP=$(kubectl config view | gawk 'match($0, /server: https:\/\/(.*):/, ip) {print ip[1]}')
fi
cd ..
cd TANGO-grafana/
git submodule update --init --recursive
make install-chart
echo
echo Waiting for all pods to be created and ready to use
kubectl wait --for=condition=ready --timeout=720s --all pods --all-namespaces

