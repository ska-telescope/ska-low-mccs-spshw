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


Running functional tests
^^^^^^^^^^^^^^^^^^^^^^^^
To run the functional (BDD) tests:

.. code-block:: shell-session

   make functional_test


Develop and test code
^^^^^^^^^^^^^^^^^^^^^^^^
Because of the time it takes to build images, and deploy and delete
the cluster, it is unwise to develop code against a real cluster unless
absolutely necessary. If doing so, the basic workflow is:

1. Edit code and/or tests
2. Build the image to be deployed:

   .. code-block:: shell-session

      make devimage

3. Deploy the built image

   .. code-block:: shell-session

      make deploy


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

      kubectl -n integration logs PODNAME

5. Once the cluster is fully deployed, run the tests:

   .. code-block:: shell-session

      make functional_test
      
6. Test failed?

   * If the problem is in the test itself, you can edit it, then
     run it again -- there is no need to delete and redeploy the
     cluster:

     .. code-block:: shell-session

        make functional_test

   * If the code needs to be edited, then, once you have edited the
     code, you will need to rebuild the image, and redeploy the cluster.
     You can either do a lightweight teardown and redeploy of just the
     MCCS pods:

     .. code-block:: shell-session

        make devimage
        make bounce
        make watch  # until pods have come back up.

     or a full teardown and redeploy of the whole cluster, including the
     tango pods:

     .. code-block:: shell-session

        make devimage
        make delete
        make watch  # until all resources are gone
        make deploy
        make watch  # or make wait

7. Run the test again, rinse, repeat.


Running a CLI
^^^^^^^^^^^^^
SKA Low MCCS has several simple CLIs that can be used to control devices
running in a cluster:

`make cli`

then

.. code-block:: shell-session

   tango@mccs-mccs-test:/app$ mccs-master 
   NAME
       mccs-master - test

   SYNOPSIS
       mccs-master - COMMAND

   DESCRIPTION
       Command-line tool to access the MCCS master tango device

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

   tango@mccs-mccs-test:/app$ mccs-master adminmode
   ONLINE


Run an interactive session with itango
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An interactice itango session can be run using `make itango`:

.. code-block:: shell-session

   ska-mccs:ska-low-mccs$ make itango
   kubectl exec -it -n integration itango-tango-base-test  -- itango3
   ITango 9.3.1 -- An interactive Tango client.

   Running on top of Python 3.7.3, IPython 7.13 and PyTango 9.3.1

   help      -> ITango's help system.
   object?   -> Details about 'object'. ?object also works, ?? prints more.

   IPython profile: tango

   hint: Try typing: mydev = Device("<tab>

   In [1]: tile = DeviceProxy("low/elt/tile_6")

   In [2]: tile.adminMode
