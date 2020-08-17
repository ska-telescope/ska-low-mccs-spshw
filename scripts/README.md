TANGO-grafana with MCCS Dashboard
=================================
Initial set of commits with the goal of setting up the TANGO-grafana project with an MCCS dashboard (all within Kubernetes).

Pre-requisites
--------------
See K8S-README.md

Set-up Script
-------------
setup_tango_grafana.sh:
Clones TANGO-grafana and skampi projects
Deploys tango-base and webjive Helm charts (this takes about 8 minutes to install on my VM)
Wait for Helm charts to be deployed
Install Traefix with detected server IP address
Install TANGO-grafana chart
Wait for chart to be installed

Tear-down Script
----------------
tear_down.sh:
Stops and deletes minikube
Removes residual files
Removes cloned repositories

Remaining work
--------------
1. Simplify TANGO-grafana install (Helm chart? But we still need to clone right?)
2. Simplify skampi install. Do we always need to clone?

