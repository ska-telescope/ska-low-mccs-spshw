SKA-Low-MCCS
============

This project is developing the Local Monitoring and Control (LMC) prototype for the [Square Kilometre Array](https://skatelescope.org/).

Documentation
-------------

[![Documentation Status](https://readthedocs.org/projects/ska-telescope-ska-low-mccs/badge/?version=latest)](https://developer.skatelescope.org/projects/ska-low-mccs/en/master/?badge=latest)

The documentation for this project, including how to get started with it, can be found in the `docs` folder, and can be better browsed in the SKA development portal:

* [MCCS LMC Prototype documentation](https://developer.skatelescope.org/projects/ska-low-mccs/en/latest/index.html "SKA Developer Portal: MCCS LMC Prototype documentation")

Setting up development environment
----------

To develop in the MCCS repo there are a number of tools and programs that you will need
such as docker, tango, mariadb and I'm sure many more to come.

Provided with the repo is are two ways to install all of these tools easily
without having the go through the fuss yourself (and mess up your PC by
installing something in the wrong place like I've done twice now)

You can use either the shell script install_script.sh or the ansible playbook
install_ansible.yml depending on which you are more familiar with.

NOTE: These scripts should only be used with debian/ubuntu flavoured linux machines
as they have not been tested with others and may not work
To use the shell script simply call the install script script, passing it one argument
which will be the password for your sql database. So something like

       ./install_script <mypassword>

You will be asked to provide your sudo password when this script runs as well as
permission to install files, type yes to all of these.

Because severel of the tasks in the ansible playbook
require root privilege you will need to call it with
the flag --ask-become-pass and provide it with both the sql password as before.

       ansiblie-playbook -e "SQL_PASSWORD=<mypassword>" --ask-become-pass

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
       me@local:~/ska-low-mccs$ docker run --rm -ti -v `pwd`:/app artefact.skao.int/ska-tango-images-pytango-builder:9.3.16
       root@caa98e8e264d:/app#

4. Install project dependencies:

       root@caa98e8e264d:/app# python3 -m pip install -r requirements-dev.txt -r testing/requirements.txt

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
