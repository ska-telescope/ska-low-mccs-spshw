=====================
Using an MCCS cluster
=====================
Okay, so you've followed the instructions at the
:doc:`setup_deployment_environment` page, and you now have a working
MCCS cluster. Now what can you do with it? Here are some options:

* run our functional (BDD) tests
* develop and test your code against the cluster (not recommended)
* use a CLI to control devices
* run an interactive iTango session
* monitor and control devices with WebJive
* monitor devices with Grafana

Running functional tests
^^^^^^^^^^^^^^^^^^^^^^^^
To run the functional (BDD) tests:

.. code-block:: shell-session

   make functional-test


Develop and test code
^^^^^^^^^^^^^^^^^^^^^^^^
Because of the time it takes to build images, and deploy and delete
the cluster, it is unwise to develop code against a real cluster unless
absolutely necessary. If doing so, the basic workflow is:

1. Edit code and/or tests
2. Build the image to be deployed:

   .. code-block:: shell-session

      make devimage

3. Re-deploy with the newly built image

   .. code-block:: shell-session

      make bounce

4. Wait for the cluster to be fully deployed:

   .. code-block:: shell-session

      make watch  # to manually watch the cluster come up
      # or
      make wait  # to block until the cluster is up

   Problems with the deployment? To get an overview of container logs,
   try

   .. code-block:: shell-session

      make logs

   To view the logs of a specific pod, try
   
   .. code-block:: shell-session

      kubectl -n mccs logs PODNAME

5. Once the cluster is fully deployed, run the tests:

   .. code-block:: shell-session

      make functional-test
      
6. Test failed? Edit the code, then

     .. code-block:: shell-session

        make devimage
        make bounce
        make watch  # until pods have come back up.
        make functional-test

   Rinse, repeat. Developing against the cluster is very slow.


Running a CLI
^^^^^^^^^^^^^
SKA Low MCCS has several simple CLIs that can be used to control devices
running in a cluster:

`make cli`

then

.. code-block:: shell-session

   tango@mccs-mccs-test:/app$ mccs-controller 
   NAME
       mccs-controller - test

   SYNOPSIS
       mccs-controller - COMMAND

   DESCRIPTION
       Command-line tool to access the MCCS controller tango device

   COMMANDS
       COMMAND is one of the following:

        adminmode
          show the admin mode TODO: make writable

        allocate

        controlmode
          show the control mode TODO: make writable

        disablesubarray
          Disable given subarray

        enablesubarray
          Enable given subarray

        healthstate
          show the health state

        logginglevel
          Get and/or set the logging level of the device.

        maintenance

        off

        on

        operate

        release
          Release given subarray

        reset

        simulationmode
          show the control mode TODO: make writable

        standbyfull

        standbylow

   tango@mccs-mccs-test:/app$ mccs-controller adminmode
   ONLINE


Run an interactive session with itango
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An interactice itango session can be run using `make itango`:

.. code-block:: shell-session

   ska-low-mccs$ make itango
   kubectl exec -it -n mccs tango-base-itango-console  -- itango3
   ITango 9.3.1 -- An interactive Tango client.

   Running on top of Python 3.7.3, IPython 7.13 and PyTango 9.3.1

   help      -> ITango's help system.
   object?   -> Details about 'object'. ?object also works, ?? prints more.

   IPython profile: tango

   hint: Try typing: mydev = Device("<tab>

   In [1]: tile = DeviceProxy("low-mccs/tile/0004")

   In [2]: tile.adminMode
   Out[2]: <adminMode.MAINTENANCE: 2>

   In [3]: 


Webjive
^^^^^^^
WebJive provides a Web UI for monitoring and controlling devices in the
cluster. The MCCS charts have Webjive enabled by default, so once MCCS
is deployed, you should be able to see Webjive in your web browser, at
the cluster's IP address.

#. Find out the IP address of the cluster:

   .. code-block:: shell-session

      me@local:~$ minikube ip
      192.168.49.2
      me@local:~$


#. Open a Web browser (Webjive works best with Chrome) and navigate to
   http://192.168.49.2/mccs/taranta/devices.

#. Log in with credentials found here:
   https://github.com/ska-telescope/ska-engineering-ui-compose-utils

#. Select the **dashboard** tab on the right-hand side of the window.

#. You may now build your own dashboard, or import a dashboard from
   file. MCCS dashboards are available at ska-low-mccs/dashboards/.

Grafana
^^^^^^^
To monitor MCCS with Grafana:

#. Navigate to http://grafana.integration.engageska-portugal.pt
#. Login with user ``admin``, password ``admin``.
#. Open Dashboards -> Manage -> examples -> MCCS Device Dashboard
#. Select device: low-mccs/control/control (default)
#. Change dashboard time-span: From: now-5s To: now
#. You can then open the CLI to interact with the controller and observe changes
   in Grafana dashboard

   .. code-block:: bash

      make cli
      mccs-controller on
      mccs-controller off
