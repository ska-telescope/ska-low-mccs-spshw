#!/bin/bash

namespace_has_pods() {
    local namespace="$1"
    local output

    output=$(kubectl get pods -n "$namespace" -o name 2>/dev/null)

    [[ -n "$output" ]]
}

namespaces=(
    "ral-2"
    "ral-2-and-4"
    "ska-low-mccs-hw-tests"
)

for namespace in "${namespaces[@]}"; do
    if namespace_has_pods "$namespace"; then
        echo "There is already a deployment in use in namespace '$namespace', tear down before running tests"
        exit -1
    fi
done

echo "No deployment found, creating one..."
exit 0