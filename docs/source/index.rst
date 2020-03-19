LFAA LMC Prototype documentation
================================

This project is developing the Local Monitoring and Control (LMC) prototype for the `Square Kilometre Array`_.

.. _Square Kilometre Array: https://skatelescope.org/

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Getting started
===============
1. To set up your environment, follow the instructions on the `Tango Development Environment set up`_ page.
2. Clone our `GitLab repo`_.
3. Verify your setup::

    $ cd /usr/src/ska-docker/docker-compose
    $ make start itango #not needed if it already shows in "make status"
    $ docker exec -it -e PYTHONPATH=/hosthome/ska-logging:/hosthome/lmc-base-classes/src \
      itango python3 \
      /hosthome/lfaa-lmc-prototype/src/ska/mccs/MccsMaster.py -?
    usage :  MccsMaster instance_name [-v[trace level]] [-nodb [-dlist <device name list>]]
    Instance name defined in database for server MccsMaster :
    $ docker exec -it -e PYTHONPATH=/hosthome/ska-logging:/hosthome/lmc-base-classes/src \
      itango tango_admin --add-server MccsMaster/01 MccsMaster lfaa/master/01
    $ docker exec -it -e PYTHONPATH=/hosthome/ska-logging:/hosthome/lmc-base-classes/src \
      itango python3 \
      /hosthome/lfaa-lmc-prototype/src/ska/mccs/MccsMaster.py 01
    1|2020-03-13T05:27:15.844Z|INFO|MainThread|write_loggingLevel|SKABaseDevice.py#490|tango-device:lfaa/master/01|Logging level set to LoggingLevel.INFO on Python and Tango loggers
    1|2020-03-13T05:27:15.845Z|INFO|MainThread|update_logging_handlers|SKABaseDevice.py#169|tango-device:lfaa/master/01|Logging targets set to []
    1|2020-03-13T05:27:15.846Z|INFO|MainThread|init_device|SKABaseDevice.py#399|tango-device:lfaa/master/01|No Groups loaded for device: lfaa/master/01
    1|2020-03-13T05:27:15.846Z|INFO|MainThread|init_device|SKABaseDevice.py#401|tango-device:lfaa/master/01|Completed SKABaseDevice.init_device
    Ready to accept request

.. _Tango Development Environment set up: https://developer.skatelescope.org/en/latest/tools/tango-devenv-setup.html
.. _Gitlab repo: https://gitlab.com/ska-telescope/lfaa-lmc-prototype.git

API
===

Package skamccs
---------------

Module ska.mcss.LfaaMaster
^^^^^^^^^^^^^^^^^^^^^^^^^^
.. automodule:: ska.mccs.LfaaMaster
  :members:
  :inherited-members:
  :show-inheritance:

Module ska.mcss.MccsSubarray
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. automodule:: ska.mccs.MccsSubarray
  :members:
  :inherited-members:
  :show-inheritance:


Indices and tables
------------------
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
