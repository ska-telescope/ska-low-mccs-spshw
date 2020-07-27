#!/bin/bash
echo Stop and delete minikube
minikube stop
minikube delete
rm -rf ~/.kube/
sudo rm -rf /var/lib/kubeadm.yaml /data/minikube /var/lib/minikube /var/lib/kubelet /etc/kubernetes
echo Remove TANGO-grafana and skampi clones
rm -rf TANGO-grafana
rm -rf skampi
