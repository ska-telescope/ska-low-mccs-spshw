#!/bin/sh

kubectl get pods -n ska-low-mccs-spshw

if [ $? -e "No resources found in ska-low-mccs namespace." ];
then
    echo "No deployment found, creating one..."
    return 0
else
    echo "There is already a deployment in use, tear down before running tests"
    return -1
fi