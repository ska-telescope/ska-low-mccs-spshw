#!/bin/bash
cd skampi
make traefik EXTERNAL_IP=$(kubectl config view | gawk 'match($0, /server: https:\/\/(.*):/, ip) {print ip[1]}')
cd ..
git clone https://gitlab.com/ska-telescope/TANGO-grafana.git
cd TANGO-grafana/
git submodule update --init --recursive
make install-chart
cd ../..
make deploy_mccs
cd scripts
watch -n 5 kubectl get pods --all-namespaces # All pods should be running
