SKA-Low-MCCS
============

This project is developing the Local Monitoring and Control (LMC) prototype for the [Square Kilometre Array](https://skatelescope.org/).

Documentation
-------------

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-low-mccs/badge/?version=latest)](https://developer.skatelescope.org/projects/ska-low-mccs/en/master/?badge=latest)

The documentation for this project, including how to get started with it, can be found in the `docs` folder, and can be better browsed in the SKA development portal:

* [MCCS LMC Prototype documentation](https://developer.skatelescope.org/projects/ska-low-mccs/en/latest/index.html "SKA Developer Portal: MCCS LMC Prototype documentation")

How to use
----------

Full details of how to deploy this prototype can be found in the documentation. Briefly:

For instructions on fully deploying the project, consult the kubernetes
section in the project documentation.

For a basic environment in which devices may be tested:

1. Install and set up Git and Docker.

2. Clone the SKA-Low-MCCS repository:

       me@local:~$ git clone https://gitlab.com/ska-telescope/ska-low-mccs.git

3. Spin up a SKA Docker instance with the SKA-Low-MCCS repository
   mounted at ``/app``, and with access to a container ``bash``
   terminal session.

       me@local:~$ cd ska-low-mccs
       me@local:~/ska-low-mccs$ docker run --rm -ti -v `pwd`:/app nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest bash
       root@caa98e8e264d:/app#

4. Install project dependencies:

       root@caa98e8e264d:/app# python3 -m pip install -r requirements-dev.txt -r requirements-tst.txt

Testing and linting code, and building docs
-------------------------------------------

This project uses ``tox`` to set up the various build stages. To execute
in the development environment, simply run::

    root@caa98e8e264d:/app# tox

Three target environments are available:

* ``py37`` for testing
* ``docs`` for building documentation
* ``lint`` for linting the code.

 These can be selected using the `-e` option.

    root@caa98e8e264d:/app# tox -e py37

To use with actual tile hardware 
---------------------------

A bitfile for the FPGA (TPM 1.2) is required. It must be renamed "tpm_test.bit"
in the base directory.

The board(s) to be connected must be accessible from the host. Their IP 
address is specified in the jive configuration file: 
License
-------

As you can see from the LICENSE file, this project is under a BSD
3-clause "Revised" License.
