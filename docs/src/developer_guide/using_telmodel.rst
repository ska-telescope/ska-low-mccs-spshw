#########################
Using telmodel repository
#########################

The telmodel repository is a gitlab repo that the yanda team have created.
The idea of this repo is that it will be the central hub for all static
data that needs to be shared across teams.
Each team hosts the dta that they are responsible for themselves, and they
have the right to change/edit the data, but once you upload the data
to the telmodel repo all other teams can access, read and use it.

To read more about it see here
https://developer.skao.int/projects/ska-telmodel/en/latest/


The basics are:

Accessing the data
------------------

To access the telmodel you must first install it,

.. code-block:: bash

    poetry add ska-telmodel

Once it is installed you can access the data by

.. code-block:: python

    from ska_telmodel.data import TMData
    tmdata = TMData()
    print(tmdata['instrument/ska1_low/layout/low-layout.json'].get_dict())


Exporting data
--------------

Exporting the data is simple, create a directory called tmdata at the
top level of your repo. Place any data/files you wish to export inside
this directory.
Then add the following stage to the gitlab pipeline

.. code-block:: bash

    # Telescope model data job
    - project: 'ska-telescope/templates-repository'
      file: 'gitlab-ci/includes/tmdata.gitlab-ci.yml'

And include the tmdata build step in the Makefile

.. code-block:: bash

    include .make/tmdata.mk