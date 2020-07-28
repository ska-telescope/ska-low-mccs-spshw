#!/bin/bash
cd skampi
make traefik EXTERNAL_IP=$(kubectl config view | gawk 'match($0, /server: https:\/\/(.*):/, ip) {print ip[1]}')
cd ..
git clone https://gitlab.com/ska-telescope/TANGO-grafana.git
cd TANGO-grafana/
git submodule update --init --recursive
make install-chart
echo
echo Waiting for all pods to be created and ready to use
kubectl -n tango-grafana wait --for=condition=ready --timeout=720s --all pods
