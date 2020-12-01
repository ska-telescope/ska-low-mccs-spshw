==================================
Set up your deployment environment
==================================

The instructions at the :doc:`setup_development_environment` page will
allow you to run tests in a lightweight test harness that mocks out
Tango Controls. *This is sufficient to get you started developing.*

However, running these tests does not actually deploy Tango devices.
These instructions will allow you to set up a deployment environment so
that you can run an actual cluster of Tango devices. They are largely
independent of the instructions for setting up a development
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

2. Install minikube and helm. Again there are various way to do this. The recommended 
   way is to use the SKA provided `make` system:

   .. code-block:: bash

      git clone git@gitlab.com:ska-telescope/sdi/deploy-minikube.git
      cd deploy-minikube
      make setup  # installs everything needed


Start the cluster manager
-------------------------
1. Start minikube, still in the deploy-minikube directory:

   .. code-block:: bash

      make install # installs all the needed tools

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
declared in `charts/ska-low-mccs/data/configuration.json`.

The selection of devices to be deployed is specified in
`charts/ska-low-mccs/values.yaml`.


Deploy MCCS to a cluster
------------------------
Kubernetes / helm interaction is facilitated through `make`. There are
quite a few `make` commands. Back in the ska-low-mccs repo, the main sequence for 
deploying is:

1. Build the development image ready for deployment to the cluster:

   .. code-block:: bash

      make devimage

   This command must be rerun whenever the code is edited. The first
   time this command is run it can take a very long time because it has
   to download gigabytes of data. It may time out: just restart it.
2. Deploy the built image to the cluster:

   .. code-block:: bash

      make install-chart

   This too may take a very long time the first time it is run.

   MCCS also has a "mccs-demo" umbrella chart for deploying a separate
   configuration for demo and testing purposes. To deploy this chart
   instead, use:

   .. code-block:: bash

      make UMBRELLA_CHART_PATH=charts/mccs-demo/ install-chart


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

        $ make install-chart; make wait; make functional_test


Use
---
Now that the cluster is running, what can you do with it? See the
:doc:`use_mccs` page for some options.


Teardown
--------
Once you have finished with the deployment, you can tear it down:

.. code-block:: shell-session

   make uninstall-chart
   make watch
    
This may take a minute or so; use `make watch` to monitor
deletion.

(On completion, `minikube` is still running, but nothing is
deployed to it. There is no need to stop `minikube`)


Monitoring the cluster
----------------------
To start up a cluster:

.. code-block:: bash

   # Check the server IP address using
   kubectl config view
   # My config switched between x.x.x.3 and x.x.x.4, where only .3 worked
   # In this case, tear-down and restart minikube
   # Export Docker environment variables to Bash
   eval $(minikube docker-env)


Now deploy mccs-umbrella chart to the cluster:

.. code-block:: bash

  cd ska-low-mccs
  make devimage
  make install-chart
  make watch

If everything went smoothly, when all the pods are running...

.. code-block:: bash

   # Take a note of the server IP address
   minikube ip

Place the returned IP address and names in `/etc/hosts` file; for example if
the above returns `172.17.0.3`, add

.. code-block:: text

   172.17.0.3  integration.engageska-portugal.pt # webjive
   172.17.0.3	grafana.integration.engageska-portugal.pt
   172.17.0.3	tangogql-proxy.integration.engageska-portugal.pt

**Note** that once this has been done the "official" instances cand no longer
be accessed until these lines have been commented out.

WebJive
-------
When the pod has been created and is ready, on the local machine navigate to:
http://integration.engageska-portugal.pt/testdb/devices

Login with credentials found here: https://github.com/ska-telescope/ska-engineering-ui-compose-utils
Once you are successfully logged in, to add the MCCS dashboard, select the
**dashboard** tab and then on the right-hand side of the window, import the
dashboard from file which is called `dashboards/MCCS_webjive_health.wj`.
Click on on the **play** button to activate the dashboard.

You can then open the CLI to interact with the controller and observe changes
in the dashboard.

   .. code-block:: bash

      make cli
      mccs-controller on
      mccs-controller off

Grafana
-------

**Currently under rework**

.. code-block:: bash

   # 

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
