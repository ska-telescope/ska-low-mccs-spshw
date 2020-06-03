K8S setup
=========

Pre-requisites
--------------

Presumably you already have *docker* installed and set up. You also need to install *kubectl*, *minikube* and *helm*. (Many online *minikube* tutorials include a step to install a VM hypervisor such as *virtualbox*: ignore this, we will use *docker* for this.)

1. Install *kubectl*. There are various ways to do this. On Ubuntu, one way is:

        curl -LO https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/amd64/kubectl
        chmod +x kubectl
        sudo mv ./kubectl /usr/local/bin/kubectl

    Don't be alarmed if running `kubectl` results in a config file error. A config file will be build the first time you run *minikube*.

2. Install *minikube*. Again there are various way to do this. On Ubuntu, one way is:

        wget https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        chmod +x minikube-linux-amd64
        sudo mv minikube-linux-amd64 /usr/local/bin/minikube

    You can test your install with `minikube version`.

3. Tell *minikube* to use docker:

        minikube config set driver docker

4. Start *minikube*:

        minikube start

5. Install *helm*. Make sure it is *helm 3* you are installing, not *2*. One way to do so on Ubuntu is

        curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
        chmod +x get_helm.sh 
        ./get_helm.sh 

How to
------

k8s/helm interaction is facilitated through `make`. For example the helm chart can be inspected with `make show`.

To start up the cluster:

```bash
make deploy_all # starts up tango-base and mccs
# see it starting up (CTRL-C to exit)
make watch # Patience is a virtue in the world of k8s
# show tango device logs
make logs
# interact
make itango
# or
make cli
# shutdown
make delete_all # or make delete for just mccs
```

Notes
-----

The tango-base chart is not strictly needed as it is in **skampi** but is here
to allow for independent testing. make sure that `HELM_RELEASE` and `KUBE_NAMESPACE` match though.
You can then use tango-base charts from **skampi**. clone the repo and start the chart from there then use `make deploy` and `make delete` to control the mccs chart ,

Tango device server configuration
---------------------------------

Device server configuration is located in _charts/mccs/data/configuration.yml_ and device containers get declared in _charts/mccs/templates/mccs.yaml_. To add e.g. a new subarray modify these two files. Make sure that `make delete` is called before modifying these and then start up with `make deploy`.
At the moment _master_, two _subbarrays_, two _stations_ and one _tile_ are spun up.

Development
-----------

To run and test from a local MCCS docker image run:

```bash
make delete
eval $(minikube docker-env)
docker build -t nexus.engageska-portugal.pt/ska-docker/ska-low-mccs:latest .
make deploy
```

Example output
--------------

### Logs

```
ska-mccs:ska-low-mccs$ make logs
---------------------------------------------------
Main Pod logs for pod/mccs-mccs-test
---------------------------------------------------
Container: mccsmaster

1|2020-05-15T05:11:48.496Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/master|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:48.496Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/master|Logging targets set to []
1|2020-05-15T05:11:48.496Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/master|No Groups loaded for device: low/elt/master
1|2020-05-15T05:11:48.496Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/master|Completed SKABaseDevice.init_device
---------------------------------------------------
Container: mccssubarray1

Before retry #1: sleeping 0.3 seconds
1|2020-05-15T05:11:49.400Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/subarray_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:49.400Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/subarray_1|Logging targets set to []
1|2020-05-15T05:11:49.400Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/subarray_1|No Groups loaded for device: low/elt/subarray_1
1|2020-05-15T05:11:49.400Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/subarray_1|Completed SKABaseDevice.init_device
1|2020-05-15T05:11:49.400Z|INFO|MainThread|init_completed|subarray.py#158|tango-device:low/elt/subarray_1|MCCS Subarray device initialised.
---------------------------------------------------
Container: mccssubarray2

1|2020-05-15T05:11:49.253Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/subarray_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:49.253Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/subarray_2|Logging targets set to []
1|2020-05-15T05:11:49.253Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/subarray_2|No Groups loaded for device: low/elt/subarray_2
1|2020-05-15T05:11:49.253Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/subarray_2|Completed SKABaseDevice.init_device
1|2020-05-15T05:11:49.253Z|INFO|MainThread|init_completed|subarray.py#158|tango-device:low/elt/subarray_2|MCCS Subarray device initialised.
---------------------------------------------------
Container: mccsstation1

1|2020-05-15T05:11:49.546Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/station_1|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:49.547Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/station_1|Logging targets set to []
1|2020-05-15T05:11:49.547Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/station_1|No Groups loaded for device: low/elt/station_1
1|2020-05-15T05:11:49.547Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/station_1|Completed SKABaseDevice.init_device
---------------------------------------------------
Container: mccsstation2

1|2020-05-15T05:11:49.913Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/station_2|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:49.913Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/station_2|Logging targets set to []
1|2020-05-15T05:11:49.914Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/station_2|No Groups loaded for device: low/elt/station_2
1|2020-05-15T05:11:49.914Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/station_2|Completed SKABaseDevice.init_device
---------------------------------------------------
Container: mccstile47

1|2020-05-15T05:11:50.087Z|INFO|MainThread|write_loggingLevel|base_device.py#527|tango-device:low/elt/tile_47|Logging level set to LoggingLevel.INFO on Python and Tango loggers
1|2020-05-15T05:11:50.087Z|INFO|MainThread|update_logging_handlers|base_device.py#236|tango-device:low/elt/tile_47|Logging targets set to []
1|2020-05-15T05:11:50.087Z|INFO|MainThread|init_device|base_device.py#436|tango-device:low/elt/tile_47|No Groups loaded for device: low/elt/tile_47
1|2020-05-15T05:11:50.087Z|INFO|MainThread|init_device|base_device.py#438|tango-device:low/elt/tile_47|Completed SKABaseDevice.init_device
1|2020-05-15T05:11:50.087Z|INFO|MainThread|init_device|tile.py#90|tango-device:low/elt/tile_47|MccsTile init_device complete
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

In [1]: tile = DeviceProxy("low/elt/tile_47")

In [2]: tile.adminMode
```

### CLI

`make cli`

then

```
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
