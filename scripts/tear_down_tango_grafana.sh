#!/bin/bash
echo Tear down Tango Grafana elements
cd skampi
make deploy HELM_CHART=archiver VALUES=../enableArchiver.yaml
cd ../..
make delete
cd scripts/TANGO-grafana/
make uninstall-chart
cd ../skampi
make delete_traefik
make delete HELM_CHART=tango-base
cd ..
echo Remove TANGO-grafana and skampi clones
rm -rf TANGO-grafana
rm -rf skampi

