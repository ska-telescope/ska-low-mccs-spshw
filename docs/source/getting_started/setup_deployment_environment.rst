==================================
Set up your deployment environment
==================================

The instructions at the :doc:`setup_development_environment` page will
allow you to run tests in a lightweight test harness that mocks out
Tango Controls. Running these tests does not actually deploy Tango
devices. These instructions will allow you to set up a deployment
environment so that you can run an actual cluster of Tango devices. They
are largely independed of the instructions for setting up a development
environment: you can follow these instructions to set up a deployment
environment on the same machine as your development environment, or on
a completely different machine.

These instructions assume a Linux environment; it should be possible to
deploy in other environments.


Initial setup
-------------
As with all SKA subsystems, SKA Low MCCS uses Helm to deploy Kubernetes
clusters of Docker containers.

1. If you are setting up on a machine that has not already been set up
   with a development environment, then you will need to install Docker,
   install Git, and clone our repo; follow the instructions at
   :doc:`setup_development_environment`.
2. Install kubectl. There are various ways to do this. On Ubuntu, one
   way is:

   .. code-block:: bash

      curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
      chmod +x kubectl
      sudo mv ./kubectl /usr/local/bin/kubectl

   Don't be alarmed if running `kubectl` results in a config file error.
   A config file will be build the first time you run minikube.

2. Install minikube. Again there are various way to do this. On Ubuntu,
   one way is:

   .. code-block:: bash

      wget https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
      chmod +x minikube-linux-amd64
      sudo mv minikube-linux-amd64 /usr/local/bin/minikube

   You can test your install with `minikube version`.

3. Tell minikube to use docker:

   .. code-block:: bash

      minikube config set driver docker


5. Install helm. Make sure it is helm 3 you are installing, not 2. One
   way to do so on Ubuntu is

   .. code-block:: bash

      curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
      chmod +x get_helm.sh 
      ./get_helm.sh 

Start the cluster manager
-------------------------
1. Start minikube:

   .. code-block:: bash

      minikube start

   There is no harm in leaving minikube running all the time, in which
   case you will only need to re-run this command after a machine
   reboot.

2. **IMPORTANT** Because we are using docker as our driver, the
   environment must be set in your terminal. This command must be run in
   each new terminal:

   .. code-block:: bash

      eval $(minikube docker-env)


MCCS cluster configuration
--------------------------
The set of all deployable devices, with suitable configurations, is
declared in `charts/mccs/data/configuration.json`.

The selection of devices to be deployed is specified in
`charts/mccs/templates/values.yaml`.


Deploy MCCS to a cluster
------------------------
Kubernetes / helm interaction is facilitated through `make`. There are
quite a few `make` commands. The main sequence for deploying is:

1. Build the development image ready for deployment to the cluster:

   .. code-block:: bash

      make devimage

   This command must be rerun whenever the code is edited. The first
   time this command is run it can take a very long time because it has
   to download gigabytes of data. It may time out: just restart it.
2. Deploy the built image to the cluster:

   .. code-block:: bash

      make deploy

   This too may take a very long time the first time it is run.
3. Monitor the cluster to make sure it comes up okay. There are two
   tools available for this:

   * To monitor the cluster yourself:
   
     .. code-block:: bash
   
        make watch
        
     After the image has been deployed to the cluster, you should see
     the device containers be created, and then the devices initialise.
     At first some devices may error; this is normal, and they will be
     automatically restarted. After several minutes, the cluster should
     stabilise and you will see that all devices are `Running`.

   * To block until the cluster is ready:

     .. code-block:: bash
   
        make wait
        
     Because this option blocks until the cluster is ready, it can be
     useful for queueing up commands:
   
     .. code-block:: shell-session

        $ make deploy; make wait; make functional_test


Use
---
Now that the cluster is running, what can you do with it? See the
:doc:`use_mccs` page for some options.


Teardown
--------
Once you have finished with the cluster, you can tear it down:

.. code-block:: shell-session

   make delete
   make watch
    
This may take a minute or so; use `make watch` to monitor
deletion.

(On completion, minikube is still running, but nothing is
deployed to it. There is no need to stop minikube.)


Monitoring the cluster with TANGO-grafana
-----------------------------------------
To start up a TANGO-grafana cluster:

.. code-block:: bash

   # Check the server IP address using
   kubectl config view
   # My config switched between x.x.x.3 and x.x.x.4, where only .3 worked
   # In this case, tear-down and restart minikube
   # Export Docker environment variables to Bash
   eval $(minikube docker-env)

Currently, to start up TANGO-grafana with the changes to the MCCS
Helm charts, need to run up the mccs pods first, if not running:

.. code-block:: bash

  cd ska-low-mccs
  make devimage
  make deploy
  make watch

After which, continue with the grafana setup:

.. code-block:: bash

   # Navigate to the MCCS scripts folder
   cd ska-low-mccs/scripts
   # Run setup script - installs tango-base, webjive, Traefik and
   # TANGO-grafana charts
   ./setup_tango_grafana.sh

Instantiate WebJive
-------------------
To start up WebJive in the cluster (continuing on from the previous instructions):

.. code-block:: bash

   # Navigate to the SKAMPI folder
   cd skampi
   # Deploy the WebJive Helm chart
   make deploy HELM_CHART=webjive

When the pod has been created and is ready, on the local machine navigate to:
http://integration.engageska-portugal.pt/testdb/devices

Login with credentials found here: https://github.com/ska-telescope/ska-engineering-ui-compose-utils


Tidy-up resources
-----------------

.. code-block:: bash

   # Remove tango grafana elements
   cd ska-low-mccs/scripts
   ./tear_down_tango_grafana.sh

If you need to tear down minikube:

.. code-block:: bash

   # If your k8s cluster is broken... 
   cd ska-low-mccs/scripts/
   ./tear_down_minikube.sh
   exit

If everything went smoothly, when all the pods are running...

.. code-block:: bash

   # Take a note of the server IP address
   kubectl config view | grep server:

Place IP address and names in /etc/hosts file; for example

.. code-block:: text

   172.17.0.3	grafana.integration.engageska-portugal.pt
   172.17.0.3	tangogql-proxy.integration.engageska-portugal.pt


To monitor MCCS with Grafana:

1. Navigate to http://grafana.integration.engageska-portugal.pt
   (admin:admin).
2. Open Dashboards -> Manage -> examples -> MCCS Device Dashboard
3. Select device: low-mccs/control/control (default)
4. Change dashboard time-span: From: now-5s To: now
5. You can then open the CLI to interact with the controller and observe changes
   in Grafana dashboard

   .. code-block:: bash

      make cli
      mccs-controller on
      mccs-controller off
