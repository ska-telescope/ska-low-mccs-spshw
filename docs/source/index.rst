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
    $ docker exec -it -e PYTHONPATH=/hosthome itango python3 \
      /hosthome/lfaa-lmc-prototype/skamccs/LfaaMaster/LfaaMaster.py -?
    usage :  LfaaMaster instance_name [-v[trace level]] [-nodb [-dlist <device name list>]]
    Instance name defined in database for server LfaaMaster :


.. _Tango Development Environment set up: https://developer.skatelescope.org/en/latest/tools/tango-devenv-setup.html
.. _Gitlab repo: https://gitlab.com/ska-telescope/lfaa-lmc-prototype.git

API
===

Package skamccs
---------------

Module skamcss.LfaaMaster
^^^^^^^^^^^^^^^^^^^^^^^^^
.. automodule:: skamccs.LfaaMaster.LfaaMaster
  :members:
  :inherited-members:
  :show-inheritance:


Indices and tables
------------------
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
