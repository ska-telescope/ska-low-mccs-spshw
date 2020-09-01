Set up Visual Studio Code
=========================
This page describes how to set up Visual Studio Code (vscode) for remote
container development in a SKA Software docker container.

The instructions below assume that you have already followed the
instructions for setting up your development environment, using the
Docker approach on the :doc:`setup_development_environment` page.

Background
----------
The remote container development workflow that we introduced in the
:doc:`setup_development_environment` is not uncommon, and is now
supported by some IDEs. The SKA-Low-MCCS repository is already set up
for remote container development in Visual Studio Code ("vscode"), and
it is recommended that you use vscode to develop.


Instructions
------------
The following instructions simply integrate our remote container
development workflow into the vscode IDE, so that, for example, the
vscode IDE terminal runs inside a Docker container.

1. Install vscode on your local machine. (On Ubuntu this is done via the
   "Ubuntu Software" app.)

2. Start vscode. Choose "Open folder..." and select the SKA-Low-MCCS
   repository folder. You should see the contents of our repository open
   into your sidebar. (If you don't: there is a column of icons along
   the left-hand side that controls which sidebar you are seeing. Click
   on the first one. *Now* you should set the contents of our repo in
   the sidebar.)

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

5. Visual Studio Code is now running inside your container. Open a bash
   terminal in vscode (look for the + button amongst the terminal
   options). The bash prompt will be something like

   .. code-block:: shell-session

     tango@18a8d6ab7934:/workspaces/ska-low-mccs$

   indicating that you are user "tango" in a docker container named
   "18a8d6ab7934" (your container name will differ).

6. Run the tests:

   .. code-block:: shell-session

     tango@18a8d6ab7934:/workspaces/ska-low-mccs$ tox -e py

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
