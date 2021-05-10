Set up your development environment
===================================
This page is part of the :doc:`getting_started` documentation for the
SKA Low MCCS subsystem.

Background
----------
Like many SKA Software projects, the SKA Low MCCS subsystem codebase is
built on some heavy dependencies, particularly Tango Controls. So in
order to run and test SKA-Low-MCCS, you will need a development
environment in which those dependencies are installed. This can be a
complicated process.

The obvious solution - to install the dependencies directly into your
local system - is not supported because:

* SKA Software developers use a range of local system types, and we
  don't want to have to support them all. It is preferable to provide
  all developers with a *consistent* environment.

* Many SKA Software developers also work on other projects, and it can
  be problematic maintaining a single environment to support multiple
  projects, each with their own set of dependencies. It is better to
  provide developers with an *isolated* environment just for SKA
  Software development.

For these reasons, the supported approaches are based on virtualisation.
There are two options:


.. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258

1. (Legacy solution) Install a hypervisor (i.e. a virtual machine
   runner) such as VirtualBox, and use that hypervisor to spin up an
   Ubuntu 18.04 virtual machine. From there, the installation process
   has been mostly automated with Ansible playbooks.

   In this approach, all SKA Software development is done in that
   virtual machine, ensuring a consistent and isolated environment.
   
   This approach is fully documented at the `SKA software developer
   portal`_. Note that:

   * The Ansible playbooks have been known to stall, for example if
     you have unreliable network connectivity.
       
   * We have found the end result to be somewhat brittle. There are
     some oddities in the setup (such as symlinks from one version of
     a python shared library to another) that mean that you can easily
     break the system doing things that you would expect to be benign
     (such as upgrading python or installing ``venv``). You are
     therefore not recommended to use this system for other
     development.

   * SKA uses Docker and kubernetes for deployment and orchestration
     of devices, and it is not recommended to run Docker and
     kubernetes from inside a virtual machine. You are going to have
     to get used to deploying your code to a Docker container
     eventually, so...


   .. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258

2. (*Recommended solution*) Instead of spinning up a full virtual
   machine, we will do our development inside a Docker container. (A
   Docker container is somewhat like a virtual machine, but it is very
   lightweight and streamlined, containing only what is needed for the
   job it was built for; and it is very easy to specify and share Docker
   images.)
   
   The advantages of this approach are:
   
   * SKA Software already has Docker images that contain all of the
     dependencies that you need to develop. These images are kept up to
     date, so you won't need to worry about maintaining your system.
     They also represent the 'canonical' SKA Software development
     environment: if your code runs on the SKA Docker image, your code
     *runs*.

   * The only local system requirements are Git and Docker. Beyond that,
     you are free to work on any operating system, to use your favourite
     IDE, and generally to set up your local system as you please.


   .. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258

   Note, however, that this approach can only be relied upon to allow
   you to develop on the SKA Low MCCS subsystem. If you need to
   contribute to other parts of the SKA Software codebase, you may find
   that you are unable to do so, if, for example, your host machine is
   running Windows.

   Detailed instructions for this follow.


SKA development with Docker
---------------------------
The basic steps for this, regardless of operating system, are

1. Install and setup Git;

2. Clone the SKA-Low-MCCS repository;

3. Install Docker;

4. Start up a ``ska-python-buildenv`` docker container, with your code
   repository mounted inside it, and with access to a bash terminal
   session.

You can now edit your code locally, but use the container terminal to
run your code inside the container.


Git
^^^
1. Install git. This should be simple on any operating system.

2. Set up git:

   .. code-block:: shell-session

     me@local:~$ git config --global user.name "Your Name"
     me@local:~$ git config --global user.email "youremail@domain.com"

3. At some point you will need to set up git commit signing too. Now is
   as good a time as any. Follow the instructions at the SKA `Working
   with Git`_ page.

4. Clone the SKA-Low-MCCS repository:

   .. code-block:: shell-session

     me@local:~$ git clone https://gitlab.com/ska-telescope/ska-low-mccs.git


Great, now it's time to dive into Docker.


Docker
^^^^^^
Installing Docker should be fairly simple on any operating system.

Windows-specific instructions
`````````````````````````````
On Windows, it is highly recommended to set up WSL2 first, as Docker
runs faster when integrated with WSL2. To set up WSL2, follow the
instructions at
https://docs.microsoft.com/en-us/windows/wsl/install-win10.

The Docker package to be installed on Windows is "Docker Desktop for
Windows". Before installing, ensure that any older Docker versions (such
as Docker Toolbox) are fully uninstalled, and that all Docker
environment variables have been deleted. Installing is very
straight-forward: simply download and run the installer.

Warning: By default, Docker Desktop enables the Hyper-V feature of
Windows. Some people find that this interferes in the operation of other
hypervisors such as VirtualBox.

If using WLS2, open the Docker Desktop for Windows dashboard, go into
Settings | Resources | WSL Integration, and ensure Docker is integrated
with your chosen WSL2 distro.

Ubuntu-specific instructions
````````````````````````````
These instructions assume Ubuntu 20.04 LTE, but may be relevant to
other versions / Linux variants.

1. Install Docker CE. Unfortunately you can't just ``sudo apt install
   docker`` because that would install a Canonical build of Docker named
   Docker.io, and this is not recommended. We'll need to work a little
   harder to install Docker CE. We can use ``apt`` but first we need to
   add the Docker apt repository, and in order to do that we will need
   to install the Docker repository public key, and these steps will
   themselves require installation of packages:

   .. code-block:: shell-session

     me@local:~$ sudo apt install apt-transport-https ca-certificates curl gnupg-agent software-properties-common
     me@local:~$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
     me@local:~$ sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
     me@local:~$ sudo apt-get update
     me@local:~$ sudo apt install docker-ce docker-ce-cli

2. Test your install:

   .. code-block:: shell-session

     me@local:~$ sudo docker run hello-world
     Unable to find image 'hello-world:latest' locally
     latest: Pulling from library/hello-world
     0e03bdcc26d7: Pull complete 
     Digest: sha256:6a65f928fb91fcfbc963f7aa6d57c8eeb426ad9a20c7ee045538ef34847f44f1
     Status: Downloaded newer image for hello-world:latest

     Hello from Docker!
     This message shows that your installation appears to be working correctly.
     ...

3. At this point you can only run this command as sudo, because you are
   not a member of the docker group. The docker group is created but it
   is empty. Add yourself to the docker group:

   .. code-block:: shell-session

     me@local:~$ sudo usermod -aG docker $USER

4. Log out and log back in. Then verify that you can run docker without
   sudo:

   .. code-block:: shell-session

     me@local:~$ docker run hello-world

Great! You are ready to run a SKA Docker container.


Build the docs
^^^^^^^^^^^^^^
Since the docs ultimately need to build successful on ReadTheDocs, we
we test our docs build by building them in a ReadTheDocs build
container. This is managed through the project makefile:

.. code-block:: shell-session

  me@local:~$ make docs


Developing in a SKA Docker container the manual way
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
From here, you can either manually set up a SKA Docker development
container, or, if you have an IDE that supports remote container
development, you can let your IDE do it for you.

The instructions that follow in this section are for manually setting up
a SKA Docker development container. The next section describes how to do
the same thing within the Visual Studio Code IDE. So you could skip this
section if you want to use the VScode IDE. On the other hand, it won't
hurt to work through this section, and it might lead to a better
understanding of what your IDE is doing for you.

1. Spin up a SKA Docker instance with the SKA-Low-MCCS repository
   mounted at ``/app``, and with access to a container ``bash``
   terminal session.

   .. code-block:: shell-session

     me@local:~$ cd ska-low-mccs
     me@local:~/ska-low-mccs$ docker run --rm -ti -v `pwd`:/app nexus.engageska-portugal.pt/ska-docker/ska-python-buildenv:latest bash
     root@0852a572ffff:/app#

   (The first time you run this command, it may take a very long time.
   This is because the Docker image has to be downloaded. Once
   downloaded, the image is cached, so the command will run much faster
   in future.)

   Note the change in prompt. You are now the root user in a bash
   terminal session that is running inside a Docker container named
   "caa98e8e264d" (the name of your container will differ).

2. List the contents of the current ``/app`` directory; you will see
   that the repository is mounted inside the container:
     
   .. code-block:: shell-session

     root@0852a572ffff:/app# ls
     CHANGELOG   README.md   demos                 requirements-lint.txt  setup.py  values-demo.yaml         values-test.yaml
     Dockerfile  build       docs                  requirements.txt       src       values-development.yaml
     LICENSE     charts      pogo                  scripts                testing   values-gitlab-ci.yaml
     Makefile    dashboards  requirements-dev.txt  setup.cfg              tox.ini   values-psi.yaml
     

3. Before you can run tests in the Docker container, you need to install
   the SKA-Low-MCCS dependencies. Run this command (inside your
   container):

   .. code-block:: shell-session

     $ root@0852a572ffff:/app# python3 -m pip install -r requirements-dev.txt -r requirements-lint.txt -r testing/requirements.txt
     
4. Hooray, your container now has all dependencies installed, and can
   now run the tests. To run the tests (inside the container):

   .. code-block:: shell-session

     $ root@0852a572ffff:/app# tox


Tox commands you may find useful:

* ``tox -e py37`` - run the tests

* ``tox -e lint`` - lint the code (with flake8)

* ``tox -e py37 -- -k MccsController`` - run the tests for just the
  MccsController device (the ``--`` argument tells tox to pass all
  subsequent arguments to pytest, and the ``-k MccsController`` tells pytest
  to run only commands that match the string ``MccsController``.


Since the repository is mounted in the container, it is possible to edit
the code from inside the container. However this is not recommended:
recollect that Docker containers are deliberately lightweight and
streamlined, containing nothing that isn't needed for them to do their
job. This Docker container was built to run SKA Software python code
against Tango Controls; it was not built for you to edit code in. It
doesn't even contain ``vi``! You could install what you need, but it
makes more sense to edit your code in your local system, where you
have your favourite IDE, and everything else you need, set up just the
way you like it. Then, after saving your changes, switch over to the
container terminal session to run the tests.

.. _SKA software developer portal: https://developer.skatelescope.org/
.. _Tango Development Environment set up: https://developer.skatelescope.org/en/latest/tools/tango-devenv-setup.html
.. _Working with Git: https://developer.skatelescope.org/en/latest/tools/git.html
.. _Gitlab repo: https://gitlab.com/ska-telescope/ska-low-mccs.git

