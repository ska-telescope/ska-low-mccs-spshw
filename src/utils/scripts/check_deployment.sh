#!/bin/bash

output=$(kubectl get pods -n ral-2 2>&1)

if [[ $output == *"No resources found"* ]];
then
    echo "No deployment found, creating one..."
    exit 0
else
    echo "There is already a deployment in use, tear down before running tests"
    exit -1
fi