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

Machine requirements
--------------------

Memory requirements
^^^^^^^^^^^^^^^^^^^
As described below, MCCS uses the SKA `deploy-minikube` project to
manage cluster deployment. By default, `deploy-minikube` requests 8Gb of
memory for minikube. This implies that, assuming you want to be able to
do other things with your computer while minikube is running, you will
need upwards of 12Gb of memory.

Actually, the MCCS chart currently requires only about 3Gb of memory, so
if you need to deploy on a memory-constrained machine, it should be okay
to overrule the `deploy-minikube` default with a setting of 4Gb or even
slightly less.

Team members have managed to deploy on hardware with even less memory,
but they were restricted to deploying minimal charts, and experienced
difficulties running other applications at the same time.

(Note that, operationally, the number of devices deployed by MCCS will
increase over time by several orders of magnitude, eventually
outstripping the capacity of any development machine. MCCS will maintain
smaller "development" charts, that deploy a small number of
representative devices, for development, demonstration and testing
purposes. These charts are not expected to grow very much larger than
they are at present, so it is probably safe to assume that an MCCS
development chart will not require more than 4Gb of memory.)


CPU requirements
^^^^^^^^^^^^^^^^
CPU requirements are much more forgiving; if you have less CPU
available, MCCS will mostly just run more slowly.

However, Tango commands timeout after three seconds (by default), and
some MCCS commands currently take not much less than that to run. So if
you deploy MCCS on a machine with slow or busy CPU, you may find that
these commands exceed the three second limit, resulting in timeout
issues. (These slow commands should not exist. MCCS plans improvements
in this area. So in future, these timeouts will not be an issue.)

By default, `deploy-minikube` tells minikube to use two CPUs. As a rough
rule of thumb: you probably won't see timeouts if minikube can get the
two CPUs that it asks for; but if there is contention for those CPUs,
you may see timeouts.


Overview of setup / teardown
----------------------------
Installation and configuration of the cluster is handled by the SKA
``deploy-minikube`` project. Thus, this project need only handle the
deployment of our project charts to the cluster.

The following state chart summarises the steps to deploying MCCS.
Detailed instructions follow.

.. image:: setup_overview.uml


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

#. Use ``deploy-minikube`` to install and configure the cluster:

   .. code-block:: bash

      make all

   If deploying to a memory-constrained machine, the memory provided to
   minikube can be reduced from the 8Gb default:

    .. code-block:: bash

       make MEM=4096mb all

   The number of CPUs that minikube is allowed to use can also be
   changed from the default of 2:

   .. code-block:: bash

      make CPUS=4 all

   Note that to change these resource values on a cluster that has
   already been deployed, it must first be deleted:

   .. code-block:: bash

      make delete
      make MEM=16384mb CPUS=8 all

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

   MCCS also has a "demo" chart configuration for deploying a separate
   configuration for demo and testing purposes. To deploy this instead,
   use:

   .. code-block:: bash

      make VALUES_FILE=values-demo.yaml install-chart

   Similarly, if you want to deploy on the PSI cluster this can be
   controlled using the `VALUES_FILE=values-psi.yaml` environment
   variable. For PSI which is on a shared cluster it is also recommended
   to set the `RELEASE_NAME`:

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
     stabilise and you will see that all devices are `Running` (except
     for the configuration pod, which will be `Completed`).

   * To block until the cluster is ready:

     .. code-block:: bash
   
        make wait

     Because this option blocks until the cluster is ready, it can be
     useful for queueing up commands. For example, to deploy MCCS, wait
     for the cluster to be ready, and then run the tests:
   
     .. code-block:: shell-session

        $ make install-chart; make wait; make functional-test

     Note that on slower machines, `make wait` may time out. This need
     not mean that there is a problem with the cluster; it is just
     taking a long time. If `make wait` is timing out for you, you won't
     be able to use it. You will need to monitor the cluster for
     readiness yourself:
   
     .. code-block:: shell-session

        $ make install-chart
        $ make watch  # watch the cluster yourself and exit when it is ready
        $ make functional-test


Using the MCCS Deployment
-------------------------
Now that the cluster is running, what can you do with it? See the
:doc:`use_mccs` page for some options.


Teardown MCCS
-------------
Once you have finished with the deployment, you can tear it down:

.. code-block:: bash

   make uninstall-chart

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
