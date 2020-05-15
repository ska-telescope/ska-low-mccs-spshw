Pre-requisite
-------------

Install *minikube* and *helm* - there are lots of tutorials on this, see also skampi documentation.

How to
------

k8s/helm interaction is faciltated through `make`. For example the helm chart can be inspected with `make show`.

To start up the cluster:

```
make deploy_all # starts up tango-base and mccs
# see it starting up (CTRL-C to exit)
make watch # Patience is a virtue in the world of k8s
# show tango device logs
make logs
# interact
make itango
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

```
make delete
eval $(minikube docker-env)
docker build -t nexus.engageska-portugal.pt/ska-docker/lfaa-mccs-prototype:latest .
make deploy
```

Example output
--------------


```
ska-mccs:lfaa-lmc-prototype$ make logs
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

itango

```
ska-mccs:lfaa-lmc-prototype$ make itango
kubectl exec -it -n integration itango-tango-base-test  -- itango3
ITango 9.3.1 -- An interactive Tango client.

Running on top of Python 3.7.3, IPython 7.13 and PyTango 9.3.1

help      -> ITango's help system.
object?   -> Details about 'object'. ?object also works, ?? prints more.

IPython profile: tango

hint: Try typing: mydev = Device("<tab>

In [1]: tile = DeviceProxy("low/elt/tile_47")                                                                                                                            

In [2]: tile.adminMode                                                                                                                                                   
Out[2]: <adminMode.ONLINE: 0>
```
