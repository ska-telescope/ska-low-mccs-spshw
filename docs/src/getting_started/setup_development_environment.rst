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
The approach described on the `SKA software developer portal`_ is a
legacy solution that is not recommended for MCCS development. Instead,
we recommend a container development approach.

The advantages of this approach are:
   
 * SKA Software already has container images that contain all of the 
   dependencies that you need to develop. These images are kept up to
   date, so you won't need to worry about maintaining your system.

 * The SKA container images are the 'canonical' SKA Software development
   environment: if your code runs on the SKA container image, your code
   *runs*.

 * The only local system requirements for developing SKA-Low-MCCS in a
   container are: a POSIX shell environment, GNU ``make``, Git and
   Docker. Other than that, you are free to work on any operating
   system, to use your favourite IDE, and generally to set up your local
   system as you please.

Basic development setup
-----------------------
The basic setup described here will allow you to edit code and
documentation locally, and to launch basic testing, linting and
documentation builds. For occasional dabblers in the MCCS code, this is
the only setup required. For more serious developers, further steps are
described in subsequent sections.

The basic steps are

1. Install Docker;

2. Install and setup Git, and clone the ska-low-mccs repository. (For
   Windows users, installing Git will also provide you with a POSIX
   shell.)

3. Install make.

Details on these steps are provided below.

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

.. warning::
   By default, Docker Desktop enables the Hyper-V feature of Windows.
   Some people find that this interferes in the operation of other
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

     me@local:~$ git clone -recurse--submodules https://gitlab.com/ska-telescope/ska-low-mccs.git


POSIX shell
^^^^^^^^^^^
The ``ska-low-mccs`` makefiles assume a POSIX shell environment. Thus,
in order to run them, you will need a POSIX shell and the ``make``
executable.

If you are running on a Linux variant (including MacOS), then your
terminal already provides a POSIX shell; for example, ``bash``.

On Microsoft Windows, neither the Command Prompt nor Powershell are
POSIX shells. There are various options for installing POSIX shells
on Windows. These include WSL2, Cygwin and MinGW. Here we take the
easiest option: your installation of Git comes with ``git-bash``, which
provides a POSIX shell (actually a copy of MinGW). Let's use that.

.. note:: If following these instructions on Windows, remember that
   whenever instructed to run a command in a local terminal, you *must*
   run it in your POSIX shell *e.g.* git-bash.

Make
^^^^
Linux instructions
``````````````````
On Linux, you can install Make via your package management system. For
example, on Ubuntu:

.. code-block:: shell-session

  me@local:~$ sudo apt install build-essential

will install a number of tools common to building tool-chains, including
Make.

Windows instructions
````````````````````
On Windows (assuming git-bash), you'll need to download a make
executable and put it where git-bash will find it:

1. Go to https://sourceforge.net/projects/ezwinports/files/

2. Download the zipfile for make (without the dependency on guile); for
   example, ``make-4.3-without-guile-w32-bin.zip``.

3. Extract the zipfile.

4. Copy the contents to your Git\\mingw64\\ folder. Merge the folders,
   but do *not* overwrite/replace any existing files.

Basic development tools
^^^^^^^^^^^^^^^^^^^^^^^
You now have a basic development setup. The following Make targets are
available to you:

* **make python-test** - run the tests in a SKA docker container
     
* **make python-lint** - run linting in a SKA docker container

Try it out:

.. code-block:: shell-session
   :emphasize-lines: 3,4,5,6,19

   me@local:~$ cd ska-low-mccs
   me@local:~/ska-low-mccs$ make python-test
   ... [output from Docker building the container image] ...
   ... [output from Docker launching the container] ...
   ... [output from poetry building its virtual environment] ...
   ... [output from pytest launching its test session] ...

   ============================= test session starts ==============================
   platform linux -- Python 3.7.3, pytest-6.2.5, py-1.11.0, pluggy-1.0.0 -- /usr/bin/python3
   cachedir: .pytest_cache

   metadata: {'Python': '3.7.3', 'Platform': 'Linux-5.13.0-28-generic-x86_64-with-debian-10.11', 'Packages': {'pytest': '6.2.5', 'py': '1.11.0', 'pluggy': '1.0.0'}, 'Plugins': {'repeat': '0.9.1', 'rerunfailures': '10.2', 'cov': '2.12.1', 'report': '0.2.1', 'xdist': '1.34.0', 'bdd': '4.1.0', 'timeout': '2.1.0', 'split': '0.6.0', 'json-report': '1.4.1', 'metadata': '1.11.0', 'forked': '1.4.0', 'pydocstyle': '2.2.0', 'pylint': '0.18.0', 'pycodestyle': '2.2.0', 'mock': '3.7.0'}}
rootdir: /workspaces/ska-low-mccs, configfile: pyproject.toml, testpaths: testing/src/
plugins: repeat-0.9.1, rerunfailures-10.2, cov-2.12.1, report-0.2.1, xdist-1.34.0, bdd-4.1.0, timeout-2.1.0, split-0.6.0, json-report-1.4.1, metadata-1.11.0, forked-1.4.0, pydocstyle-2.2.0, pylint-0.18.0, pycodestyle-2.2.0, mock-3.7.0
collected 1529 items

   testing/src/tests/integration/test_health_management.py::test_controller_health_rollup PASSED [  0%]
   testing/src/tests/functional/test_controller_subarray_interactions.py::test_allocate_subarray SKIPPED       [  0%]

   ... [lots more test results] ...

   testing/src/tests/unit/test_utils.py::TestUtils::test_json_input_schema_raises[{"subarray_id":17, "stations":["station1"]}] PASSED [ 99%]
   testing/src/tests/unit/test_utils.py::TestUtils::test_json_input_schema_raises[{"subarray_id":1, "stations":[]}] PASSED [100%]
   
   ---------------------------------- generated xml file: /app/build/reports/unit-tests.xml ----------------------------------
   ------------------------------------------------------- JSON report -------------------------------------------------------
   JSON report written to: build/reports/report.json (3921454 bytes)
   
   ----------- coverage: platform linux, python 3.7.3-final-0 -----------
   Coverage HTML written to dir build/htmlcov
   Coverage XML written to file build/reports/code-coverage.xml
   
   ================================= 1403 passed, 125 skipped, 1 xfailed, 10 warnings in 673.29s (0:11:13) ==================================
   _________________________________________________________ summary _________________________________________________________

   me@local:~/ska-low-mccs$
   
(The first time you run these commands, they may take a very long time.
This is because the Docker image has to be downloaded. Once downloaded,
the image is cached, so the command will run much faster in future.)


Advanced development setup
^^^^^^^^^^^^^^^^^^^^^^^^^^
The approach described above provides a few basic tools, but serious
developers will want more than this. For example, ``make python-test`` runs
all the tests, but serious developers will want fine-grained control of 
what tests to run.

To run tests in a specific file or directory change the ``PYTHON_TEST_FILE``
variable in the Makefile. This can also be done from the command line, for example: 
``make PYTHON_TEST_FILE=testing/src/tests/unit/tile python-test`` will run all tests 
found in the tile directory.

Since the repository is read-write mounted in the container, it is
possible to edit the code from inside the container. However this is not
recommended: Docker containers are deliberately lightweight and
streamlined, containing nothing that isn't needed for them to do their
job. This Docker container was built to run SKA Software python code,
not for you to edit code in. It doesn't even contain ``vi``. You could
install what you need, but it makes more sense to edit the code on your
local system, where you have your favourite IDE, and everything else you
need, set up just the way you like it. Then, after saving your changes,
switch over to the container terminal session to run the tests.

.. _SKA software developer portal: https://developer.skatelescope.org/
.. _Tango Development Environment set up: https://developer.skatelescope.org/en/latest/tools/tango-devenv-setup.html
.. _Working with Git: https://developer.skatelescope.org/en/latest/tools/git.html
.. _Gitlab repo: https://gitlab.com/ska-telescope/ska-low-mccs.git

IDE integration
^^^^^^^^^^^^^^^
The workflow described above - editing locally but deploying to a remote
container for testing - is well supported by IDEs. The SKA-Low-MCCS
repository is already set up for remote container development in
Visual Studio Code ("vscode"). It is highly recommended that you use
vscode to develop. To set up vscode, follow the instructions at
:doc:`setup_vscode`.
