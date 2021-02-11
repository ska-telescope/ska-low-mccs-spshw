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


Overview of setup / teardown
----------------------------
Installation and configuration of the cluster is handled by the SKA
``deploy-minikube`` project. Thus, this project need only handle the
deployment of our project charts to the cluster.

The following state chart summarises the steps to deploying MCCS.
Detailed instructions follow.

.. uml:: setup_overview.uml


Prerequisites and initial setup
-------------------------------
As with all SKA subsystems, SKA Low MCCS uses Helm to deploy Kubernetes
clusters of Docker containers.

#. If you are setting up on a machine that has not already been set up
   with a development environment, then you will need to install Docker,
   install Git, and clone our repo; follow the instructions at
   :doc:`setup_development_environment`.
#. Install kubectl. There are various ways to do this. On Ubuntu, one
   way is:

   .. code-block:: bash

      curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
      chmod +x kubectl
      sudo mv ./kubectl /usr/local/bin/kubectl

   Don't be alarmed if running `kubectl` results in a config file error.
   A config file will be build the first time you run minikube.

#. Clone the SKA ``deploy-minikube`` project. (But first, if you have
   run minikube before, remove any old copies and their configuration
   files.)
   
   .. code-block:: bash

      find / -name minikube 2>/dev/null
      sudo rm -f <path/minikube>
      rm -rf ~/.minikube

   .. code-block:: bash

      git clone git@gitlab.com:ska-telescope/sdi/deploy-minikube.git

Start the cluster manager
-------------------------
#. Check for a new version of ``deploy-minikube``. Development is ongoing,
   and you want to be running the latest version:

   .. code-block:: bash

      cd ~/deploy-minikube
      git pull

   (Obviously there is no need to do this if you have only just cloned
   the project.)

#. Used ``deploy-minikube`` to install and configure the cluster:

   .. code-block:: bash

      make all

#. **IMPORTANT** Because we are using docker as our driver, the
   environment must be set in your terminal. This command must be run in
   each new terminal:

   .. code-block:: bash

      eval $(minikube docker-env)


Deploy MCCS to a cluster
------------------------
The basic steps to deploying MCCS are:

#. Change into the ska-low-mccs directory, and build the development
   image ready for deployment to the cluster:

   .. code-block:: bash

      cd ~/ska-low.mccs
      make devimage

   The ``make devimage`` command must be rerun whenever the code is
   edited. The first time this command is run it can take a very long
   time because it has to download gigabytes of data. It may time out:
   just rerun it.

#. Deploy the built image to the cluster. The basic command is

   .. code-block:: bash

      make install-chart

   This too may take a very long time the first time it is run.

   MCCS also has a "mccs-demo" chart configuration for deploying a separate
   configuration for demo and testing purposes. To deploy this instead, use:

   .. code-block:: bash

      make VALUES_FILE=values-demo.yaml install-chart

   Similarly, if you want to deploy on the PSI cluster this can be controlled
   using the `VALUES_FILE=values-psi.yaml` environment variable.
   For PSI which is on a shared cluster it is also recommended to set:

   .. code-block:: bash

      make RELEASE_NAME=mccs-psi VALUES_FILE=values-demo.yaml install-chart

#. Monitor the cluster to make sure it comes up okay. There are two
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

        $ make install-chart; make wait; make functional-test

Using the MCCS Deployment
-------------------------
Now that the cluster is running, what can you do with it? See the
:doc:`use_mccs` page for some options.


Teardown MCCS
-------------
Once you have finished with the deployment, you can tear it down:

.. code-block:: bash

   make uninstall-chart
   make watch

This may take a minute or so; use `make watch` to monitor
deletion.

Note that this does not teardown the minikube deployment, it simply
unloads the MCCS charts.


Teardown everything
-------------------
There is no harm in leaving minikube running all the time. But if you
`must` tear everything down, then

.. code-block:: bash

   cd ~/deploy-minikube
   make clean


Set up Grafana
--------------

**Currently under rework**

In order to use Grafana to monitor the cluster, an extra step is
required: you must make your Web browser think that
grafana.integration.engageska-portugal.pt is served by your minikube
cluster.

#. Obtain the IP address of your cluster:

   .. code-block:: shell-session

      me@local:~$ minikube ip
      192.168.49.2
      me@local:~$

Add the following line to your hosts file (on Ubuntu this is located at
/etc/hosts).

.. code-block:: text

   192.168.49.2 grafana.integration.engageska-portugal.pt

See the :doc:`use_mccs` page for instructions on using Grafana.
