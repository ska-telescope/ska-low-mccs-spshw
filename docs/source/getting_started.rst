Getting started
===============

Background
----------
Like many SKA Software projects, the SKA-Low-MCCS code-base is built on some
heavy dependencies, particularly Tango Controls. So in order to run and test
SKA-Low-MCCS, you will need a development environment in which those
dependencies are installed. This is a complicated process.

The obvious solution - to install the dependencies directly into your local
system - is not supported because:

* SKA Software developers use a range of local system types, and we don't want
  to have to support them all. It is preferable to provide all developers with
  a *consistent* environment.

* Many SKA Software developers also work on other projects, and it can be
  problematic maintaining a single environment to support multiple projects,
  each with their own set of dependencies. It is better to provide all
  developers with an *isolated* environment just for SKA Software development.

For these reasons, the supported approaches are based on virtualisation. There
are two options:



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
The program you need to install is "Docker Desktop for Windows".

Before installing, ensure that any older Docker versions (such as Docker
Toolbox) are fully uninstalled, and that all Docker environment variables
have been deleted.

Installing is very straight-forward: simply download and run the installer.

Warning: Docker Desktop enables the Hyper-V feature of Windows. Some people
find that this interferes in the operation of other hypervisors such as
VirtualBox.


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
     root@caa98e8e264d:/app#

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

     root@caa98e8e264d:/app# ls
     CHANGELOG      LICENSE	  build   integration_tests	requirements-tst.txt  setup.py	tox.ini
     Dockerfile     Makefile   charts  pogo			requirements.txt      src
     K8S-README.md  README.md  docs	  requirements-dev.txt	setup.cfg	      tests

3. Before you can run tests in the Docker container, you need to install
   the SKA-Low-MCCS dependencies. Run this command (inside your
   container):

   .. code-block:: shell-session

     $ root@caa98e8e264d:/app# python3 -m pip install -r requirements-dev.txt -r requirements-tst.txt
     
4. Hooray, your container now has all dependencies installed, and can
   now run the tests. To run the tests (inside the container):

   .. code-block:: shell-session

     $ root@caa98e8e264d:/app# tox


Tox commands you may find useful:

* ``tox -e py37`` - run the tests

* ``tox -e docs`` - build the docs

* ``tox -e lint`` - lint the code (with flake8)

* ``tox -e py37 -- -k MccsMaster`` - run the tests for just the
  MccsMaster device (the ``--`` argument tells tox to pass all
  subsequent arguments to pytest, and the ``-k MccsMaster`` tells pytest
  to run only commands that match the string ``MccsMaster``.


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


Visual Studio Code integration
------------------------------

The remote-container development workflow described above is not
uncommon, and is now supported by some IDEs. The SKA-Low-MCCS repository
is already set up for remote container development in Visual Studio
Code ("vscode"), and it is recommended that you use vscode to develop.

The following instructions simply uses the vscode IDE to do what we just
did manually in the previous section.

1. Install vscode on your local system. (On Ubuntu this is done via the
   "Ubuntu Software" app.)

2. Start vscode. Choose "Open folder..." and select the SKA-Low-MCCS
   repository folder. You should see the contents of our repository open
   into your sidebar.

   * If you don't: there is a column of icons along the left-hand side
     that controls which sidebar you are seeing. Click on the first
     one. *Now* you should set the contents of our repo in the sidebar.


  .. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258

3. Click on the "Extensions" sidebar icon (it's the one that looks like
   a square jigsaw puzzle.) Search for and install "Remote-Containers".

4. Once the extension is installed, you should see a pop-up box telling
   you that it has detected a ``.devcontainers`` folder, and asking if
   you want to reload the repository in a remote container. Choose yes.
   You'll see a pop-up message that it is "Starting with Dev Container".

   * If you left it too long and the ".devcontainer detected" pop-up
     disappeared, then <Ctrl-Shift-P> is your friend: it opens a Command
     Bar from which any VScode command can be searched for and run. Type
     "Remote" and you will find an option along the lines of "Rebuild
     and reopen in container".

   * The first time you do this, it may take a very long time, because
     the Docker image has to be downloaded. Once downloaded, the image
     will be cached, so it will be much faster in future.
     
   * If you click on the "Starting with Dev Container" message box, it
     will show you a terminal where things are happening. Go have a cup
     of tea.


  .. Padding. See https://github.com/sphinx-doc/sphinx/issues/2258

5. vscode is now running inside your container. Open a bash terminal in
   vscode (look for the + button amongst the terminal options). The 
   bash prompt will be something like

   .. code-block:: shell-session

     tango@18a8d6ab7934:/workspaces/ska-low-mccs$

   indicating that you are user "tango" in a docker container named
   "18a8d6ab7934" (your container name will differ).

6. Run the tests:

   .. code-block:: shell-session

     tango@18a8d6ab7934:/workspaces/ska-low-mccs$ tox

   The tests run because they are being run inside the Docker container,
   which contains all the dependencies.

7. Go code!

   * The other sidebar you need to know about is the git sidebar. This
     sidebar helps you keep track of git status and perform git
     commands. For example, to make a commit, simply stage the edited
     files that you want to commit (the "+" button), provide a message
     in the message box, and hit the commit (tick) button. For more
     more complex git stuff like stashing, rebasing, etc, it might be
     possible to do it through the GUI, but you might still find it
     easier to do it in the terminal.

.. _SKA software developer portal: https://developer.skatelescope.org/
.. _Tango Development Environment set up: https://developer.skatelescope.org/en/latest/tools/tango-devenv-setup.html
.. _Working with Git: https://developer.skatelescope.org/en/latest/tools/git.html
.. _Gitlab repo: https://gitlab.com/ska-telescope/ska-low-mccs.git
