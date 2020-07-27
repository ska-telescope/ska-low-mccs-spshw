TANGO-grafana with MCCS Dashboard

This is an initial set of commits with the goal of setting up the TANGO-grafana project with an MCCS dashboard (all within Kubernetes). There are 3 setup scripts, a monitor script and a teardown script.

setup_part1.sh
Starts the minikube environment
Clones skampi project
Deploys tango-base and webjive (this takes about 8 minutes to install on my VM)

setup_part2.sh
Makes traefik
Clones TANGO-grafana project (requires gitlab credentials)
Makes charts
Deploys MCCS instance (this takes about 10 minutes to install on my VM)

setup_part3.sh
Install MCCS dashboard

monitor.sh
Monitors Kubernetes pods

teardown.sh
stops and deletes minikube
Removes residual files
Removes cloned repositories

Remaining work
1. Refactor deploy_mccs as this is based on previous version of MCCS master
2. Simplify TANGO-grafana install (Helm chart? But we still need clone right?)
3. Simplify skampi install. Do we always need to clone?
4. Add certain sections to MCCS makefile

