K8S setup
=========

Pre-requisites
--------------

Presumably you already have *docker* installed and set up. You also need to
install *kubectl*, *minikube* and *helm*. (Many online *minikube* tutorials
include a step to install a VM hypervisor such as *virtualbox*: **ignore** this, we
will use *docker* for this.)

1. Install *kubectl*. There are various ways to do this. On Ubuntu, one way is:

        curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
        chmod +x kubectl
        sudo mv ./kubectl /usr/local/bin/kubectl

    Don't be alarmed if running `kubectl` results in a config file error. A
    config file will be build the first time you run *minikube*.

2. Install *minikube*. Again there are various way to do this. On Ubuntu, one way is:

        wget https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        chmod +x minikube-linux-amd64
        sudo mv minikube-linux-amd64 /usr/local/bin/minikube

    You can test your install with `minikube version`.

3. Tell *minikube* to use docker:

        minikube config set driver docker

    **IMPORTANT** when using the this driver. To use docker within *minikube* the
    environment has to be set in your terminal `eval $(minikube docker-env)`

4. Start *minikube*:

        minikube start

5. Install *helm*. Make sure it is *helm 3* you are installing, not *2*. One way
   to do so on Ubuntu is

        curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
        chmod +x get_helm.sh 
        ./get_helm.sh 

How to
------

k8s/helm interaction is facilitated through `make`. For example the helm chart
can be inspected with `make show`.

**NOTE** - The first time `make devimage` and `make deploy` are run it can take
a while or time out as it has to fetch GBs of images.

To start up the cluster:

```bash
# if you haven't done so call (if you know what you are doing add to your .bashrc)
eval $(minikube docker-env)
make devimage # create a ska-low-mccs:latest docker image reflecting the repository
# "make pull" would fetch latest released one
make deploy # starts up tango-base and mccs
# see it starting up (CTRL-C to exit)
make watch # Patience is a virtue in the world of k8s
# show tango device logs
make logs
# interact
make itango
# or
make cli
# shutdown
make delete
```
At this stage there is no set up to do _interactive_ development in k8s, like
the vscode container dev environment.

To start up a TANGO-grafana cluster:
```bash
# I've found it necessary to close ALL apps before starting this sequence
cd ska-low-mccs/
# Tidy up any previous minikube environment
./scripts/tear_down.sh
exit
# Start minikube in a new terminal window
minikube start
# Now check the server IP address using
kubectl config view
# My config switched between x.x.x.3 and x.x.x.4, where only .3 worked
# In this case, close all apps and try again
# Export Docker environment variables to Bash
eval $(minikube docker-env)
# Navigate to the MCCS scripts folder
cd ska-low-mccs/scripts
# Run setup script - installs tango-base, webjive, Traefik and
# TANGO-grafana charts
./setup_tango_grafana.sh
cd ..
# Create an ska-low-mccs:latest docker image reflecting the repository
make devimage
# Set environment variable to prevent tango-base being deployed again
export TANGO_BASE_ENABLED=false
# Starts up mccs
make deploy
make watch # Patience is a virtue in the world of k8s
```

If everything went smoothly, when all the pods are running...

```bash
# Take a note of the server IP address
kubectl config view | grep server:
```

Place IP address and names in /etc/hosts file:

e.g.
172.17.0.3	grafana.integration.engageska-portugal.pt
172.17.0.3	tangogql-proxy.integration.engageska-portugal.pt

Navigate to this address in a web-browser:
URL: http://grafana.integration.engageska-portugal.pt

Log-in:
admin:admin

* Open Dashboards->Manage->examples->Tango Dashboard
* select device: low/alt/master
* Attribute list can be seen on the right hand side half way down the dashboard
* Change dashboard time-span: From: now-5s To: now
* You can then open the CLI to interact with master and observe changes in Grafana dashboard
```bash
make cli
mccs-master on
mccs-master off
```

Tango device server configuration
---------------------------------

Device server configuration is located in _charts/mccs/data/configuration.json_
and device containers get declared in _charts/mccs/templates/mccs.yaml_. To add
e.g. a new subarray modify these two files. Make sure that `make delete` is
called before modifying these and then start up with `make deploy`.
At the moment _master_, two _subbarrays_, two _stations_ and one _tile_ are spun
up.

Integration test
----------------

`make integration_test`

Development
-----------

The genral recipe will get the lates ska-low-mccs docker images from nexus.
Most likely for devlopment we want to deply teh current repository state.

To run from a local MCCS docker image execute:

```bash
eval $(minikube docker-env) # any time (run once) you have a new bash/sh
```

```bash
make delete
make devimage # will create a new  ska-low-mccs:latest (locally)
make deploy
```

The above tears down the whole deployment (including tango-base).
Alternatively device server pods can be updated with

```bash
make devimage
make bounce
make watch # the pods will stay a while in terminating. AFTER! that call
make wait # to ensure the pods are back up.
```

which will be a little faster

This *needs* to be done to deploy any changes made locally.

Example output
--------------

### Logs

```
mar637@ska-mccs:/work/mar637/repos/ska-low-mccs$ make logs
---------------------------------------------------
Logs for pod/mccs-beam1-test-0
kubectl logs -n integration pod/mccs-beam1-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
Before retry #2: sleeping 0.6 seconds
1|2020-06-25T23:14:43.156Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/beam_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.159Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/beam_1|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.159Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/beam_1|No Groups loaded for device: low/elt/beam_1
1|2020-06-25T23:14:43.159Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/beam_1|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-beam2-test-0
kubectl logs -n integration pod/mccs-beam2-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
Before retry #2: sleeping 0.6 seconds
1|2020-06-25T23:14:43.521Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/beam_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.521Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/beam_2|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.521Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/beam_2|No Groups loaded for device: low/elt/beam_2
1|2020-06-25T23:14:43.521Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/beam_2|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-beam3-test-0
kubectl logs -n integration pod/mccs-beam3-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
Before retry #2: sleeping 0.6 seconds
1|2020-06-25T23:14:43.426Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/beam_3|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.426Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/beam_3|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.426Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/beam_3|No Groups loaded for device: low/elt/beam_3
1|2020-06-25T23:14:43.426Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/beam_3|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-master-test-0
kubectl logs -n integration pod/mccs-master-test-0
---------------------------------------------------
1|2020-06-25T23:14:41.973Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/master|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:41.974Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/master|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:41.974Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/master|No Groups loaded for device: low/elt/master
1|2020-06-25T23:14:41.974Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/master|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-station1-test-0
kubectl logs -n integration pod/mccs-station1-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
Before retry #2: sleeping 0.6 seconds
1|2020-06-25T23:14:43.530Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/station_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.531Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/station_1|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.531Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/station_1|No Groups loaded for device: low/elt/station_1
1|2020-06-25T23:14:43.531Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/station_1|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-station2-test-0
kubectl logs -n integration pod/mccs-station2-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
1|2020-06-25T23:14:43.454Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/station_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.454Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/station_2|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.454Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/station_2|No Groups loaded for device: low/elt/station_2
1|2020-06-25T23:14:43.454Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/station_2|Completed SKABaseDevice.init_device
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-subarray1-test-0
kubectl logs -n integration pod/mccs-subarray1-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
1|2020-06-25T23:14:43.488Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/subarray_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.488Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/subarray_1|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.488Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/subarray_1|No Groups loaded for device: low/elt/subarray_1
1|2020-06-25T23:14:43.488Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/subarray_1|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.488Z|INFO|MainThread|init_completed|subarray.py#100|tango-device:low/elt/subarray_1|MCCS Subarray device initialised.
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-subarray2-test-0
kubectl logs -n integration pod/mccs-subarray2-test-0
---------------------------------------------------
Before retry #1: sleeping 0.3 seconds
1|2020-06-25T23:14:43.497Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/subarray_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.497Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/subarray_2|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.497Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/subarray_2|No Groups loaded for device: low/elt/subarray_2
1|2020-06-25T23:14:43.497Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/subarray_2|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.497Z|INFO|MainThread|init_completed|subarray.py#100|tango-device:low/elt/subarray_2|MCCS Subarray device initialised.
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile1-test-0
kubectl logs -n integration pod/mccs-tile1-test-0
---------------------------------------------------
1|2020-06-25T23:14:42.888Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:42.888Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_1|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:42.891Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_1|No Groups loaded for device: low/elt/tile_1
1|2020-06-25T23:14:42.891Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_1|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:42.891Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_1|MccsTile init_device complete
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile2-test-0
kubectl logs -n integration pod/mccs-tile2-test-0
---------------------------------------------------
1|2020-06-25T23:14:43.247Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.247Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_2|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.247Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_2|No Groups loaded for device: low/elt/tile_2
1|2020-06-25T23:14:43.247Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_2|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.247Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_2|MccsTile init_device complete
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile3-test-0
kubectl logs -n integration pod/mccs-tile3-test-0
---------------------------------------------------
1|2020-06-25T23:14:43.171Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_3|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.171Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_3|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.172Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_3|No Groups loaded for device: low/elt/tile_3
1|2020-06-25T23:14:43.172Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_3|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.172Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_3|MccsTile init_device complete
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile4-test-0
kubectl logs -n integration pod/mccs-tile4-test-0
---------------------------------------------------
1|2020-06-25T23:14:43.045Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_4|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.045Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_4|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.046Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_4|No Groups loaded for device: low/elt/tile_4
1|2020-06-25T23:14:43.046Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_4|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.046Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_4|MccsTile init_device complete
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile5-test-0
kubectl logs -n integration pod/mccs-tile5-test-0
---------------------------------------------------
1|2020-06-25T23:14:43.773Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_5|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.773Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_5|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.773Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_5|No Groups loaded for device: low/elt/tile_5
1|2020-06-25T23:14:43.773Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_5|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.774Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_5|MccsTile init_device complete
---------------------------------------------------

---------------------------------------------------
Logs for pod/mccs-tile6-test-0
kubectl logs -n integration pod/mccs-tile6-test-0
---------------------------------------------------
1|2020-06-25T23:14:43.734Z|INFO|MainThread|write_loggingLevel|base_device.py#587|tango-device:low/elt/tile_6|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-06-25T23:14:43.735Z|INFO|MainThread|update_logging_handlers|base_device.py#306|tango-device:low/elt/tile_6|Logging targets set to ['tango::logger']
1|2020-06-25T23:14:43.735Z|INFO|MainThread|init_device|base_device.py#510|tango-device:low/elt/tile_6|No Groups loaded for device: low/elt/tile_6
1|2020-06-25T23:14:43.735Z|INFO|MainThread|init_device|base_device.py#512|tango-device:low/elt/tile_6|Completed SKABaseDevice.init_device
1|2020-06-25T23:14:43.735Z|INFO|MainThread|init_device|tile.py#91|tango-device:low/elt/tile_6|MccsTile init_device complete
```

### itango

itango

```
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
```

### CLI

`make cli`

then

```bash
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
```
