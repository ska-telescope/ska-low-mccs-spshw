=========
Deploying
=========

As a component of the MCCS subsystem,
ska-low-mccs-spshw would not normally be deployed directly,
except for development purposes.
This guidance is aimed at developers,
and should be read in conjunction with the MCCS subsystem documentation
on deploying the MCCS subsystem as a whole.

``ska-low-mccs-spshw`` uses helmfile to configure helm values files.

---------------------
Deploy using helmfile
---------------------
To deploy ``ska-low-mccs-spshw`` onto a k8s cluster, use the command
``helmfile --environment <environment_name> sync``.
To see what environments are supported,
see the ``environments`` section of ``helmfile.d/helmfile.yaml``.

(Although helmfile supports k8s context switching, this has not yet
been set up. You must manually set your k8s context for the platform
you are targetting, before running the above command.)

To tear down a release that has been deployed by helmfile,
use the command ``helmfile <same arguments> destroy``.
It is important that the arguments to the ``destroy`` command
be the same as those used with the ``sync`` command.
For example, if the release was deployed with ``helmfile --environment gmrt sync``,
then it must be torn down with ``helmfile --environment gmrt destroy``.
If arguments are omitted from the ``helmfile destroy`` command,
the release may not be fully torn down.

--------------------------------
Deploy using the .make submodule
--------------------------------
The ``ska-low-mccs-spshw`` repo includes the ``ska-cicd-makefile`` submodule,
and thus supports the SKA-standard ``make install-chart`` and ``make uninstall-chart`` targets.
When using this approach,
use the ``K8S_HELMFILE_ENV``environment variable to specify the environment.
For example, ``make K8S_HELMFILE_ENV=aavs3 install-chart`` and
``make K8S_HELMFILE_ENV=aavs3 uninstall-chart``.

------------
How it works
------------
The ``environments`` section of ``helmfile.d/helmfile.yaml`` specifies
a sequence of helmfile values files for each environment.
The first file will generally be a specification of the target platform.
This file should only change when the platform itself changes.

The value files are applied from top to bottom. This means that subsequent value files
will override the previous. So we need to be careful and follow the guidelines. An example
is:

.. code-block:: yaml

  environments:
    psi-low-minikube:
      kubeContext: minikube
      values:
        - git::https://gitlab.com/ska-telescope/ska-psi-low.git@/helmfile.d/values/platform.yaml?ref=20895318908c03c21def95a4b0b44caa79c58b38
        - spshw/values/values-psi-low.yaml
        - platform/minikube.yaml
        - spshw/values/values-psi-low-minikube.yaml

The platform specification for PSI-Low is currently held in a remote location,
this has one subrack and two TPMs:

.. code-block:: yaml

   platform:
     metadata:
       version: 0.0.3
       description: A platform configuration specification for the PSI-Low.   

     cluster:
       domain: cluster.local
       services:
         jupyterhub: true
         taranta-platform: true
       daq:
         storage_class: nfss1
         node_selector:
           kubernetes.io/hostname: psi-node3
   
     array:
       name: psi-low
       station_clusters:
         "p1":
           stations:
             "1":
               id: 1
               name: psi-low
               sps:
                 subracks:
                   "1":
                     srmb_host: 10.0.10.80
                     srmb_port: 8081
                     nodeSelector:
                       kubernetes.io/hostname: psi-node3
                 tpms:
                   "10":
                     host: 10.0.10.218
                     port: 10000
                     version: tpm_v1_6
                     subrack: 1
                     subrack_slot: 2
                     nodeSelector:
                       kubernetes.io/hostname: psi-node3
                   "13":
                     host: 10.0.10.215
                     port: 10000
                     version: tpm_v1_6
                     subrack: 1
                     subrack_slot: 5
                     nodeSelector:
                       kubernetes.io/hostname: psi-node3

Subsequent files specify default values and overrides.
There are two keys:

* The ``defaults`` key specifies default values that are
  available to all helmfile templates.
  Currently the only supported default value is ``logging_level_default``.
  For example, to specify that the ``LoggingLevelDefault`` property
  of all Tango devices should be ``DEBUG`` (``5``):

  .. code-block:: yaml

     defaults:
       logging_level_default: 5

* The ``overrides`` key allows to set and override values
  at any place in the platform specification.
  It follows the structure of the platform specification,
  but with values to override or augment that specification.
  For example, to set the ``logging_level_default`` for a single TPM:

  .. code-block:: yaml

     overrides:
       array:
         station_clusters:
           "p1":
             stations:
               "1":
                 sps:
                   tpms:
                     "10":
                       logging_level_default: 5

  Two special keys are supported:

  * The ``enabled`` key can be applied to any device instance,
    to enable or disable deployment of that device.
    For example, to disable deployment of tpm 10:

    .. code-block:: yaml

       overrides:
         array:
           station_clusters:
             "p1":
               stations:
                 "1":
                   sps:
                     tpms:
                       "10":
                         enabled: false

    One can also disable an entire station, and then enable only certain
    devices:

    .. code-block:: yaml

       overrides:
         array:
           station_clusters:
             "p1":
               stations:
                 "1":
                   enabled: false
                   sps:
                     tpms:
                       "10":
                         enabled: true
                       "13":
                         enabled: true

  * The ``simulated`` key indicates that devices should run against a simulator,
    or should simulate their interactions with hardware.
    Not all device templates support this key,
    and those that do may handle it in various ways.
    For example the subrack device template deploys a subrack simulator
    for it to monitor and control, whereas the TPM device template
    merely puts the TPM device into simulation mode.

    For example:

    .. code-block:: yaml

       overrides:
         array:
           station_clusters:
             "p1":
               stations:
                 "1":
                   sps:
                     subracks:
                       "1":
                         simulated: true


Specifying ``2`` platforms is discouraged. 
The exception being when targeting minikube we apply ``platform/minikube.yaml``.
This is because local minikube deployments will not have the platform resources,
and will need to specify its own.

--------------------------------
Direct deployment of helm charts
--------------------------------
The `ska-low-mccs-spshw`` helm chart uses `ska-tango-devices`
to configure and deploy its Tango devices. 
For details on `ska-tango-devices`,
see its `README <hhttps://gitlab.com/ska-telescope/ska-tango-devices/-/blob/main/README.md>`_

Defining devices
~~~~~~~~~~~~~~~~
Devices are defined under `ska-tango-devices.devices`,
as a nested dictionary in which the bottom-level key is the name of a device class,
the next is the name of a device TRL,
and the last is device property names and values.
For example:

.. code-block:: yaml

  ska-tango-devices:
    devices:
      MccsTile:
        low-mccs/tile/s8-1-tpm01:
          SubrackFQDN: low-mccs/subrack/s8-1-1
          SubrackBay: 1
          TileId: 1
          StationId: 345
          TpmIp: 10.132.0.8

It is also possible to specify default values for a device class
in the `deviceDefaults` key:

.. code-block:: yaml

  ska-tango-devices:
    deviceDefaults:
     MccsTile:
       TpmCpldPort: 10000
       TpmVersion: tpm_v1_6
       AntennasPerTile: 16
       PollRate: 0.2

Defaults are applied to all devices of the specified class,
but any device-specific value provided under the `devices` key takes precedence.

Defining device servers
~~~~~~~~~~~~~~~~~~~~~~~
Device servers are specified under the `ska-tango-devices.deviceServers` key.
This contains configuration specific to the device server,
and the kubernetes pod in which it runs.

The key hierarchy is:

.. code-block:: yaml

  ska-tango-devices:
    <device_server_type>:
      <device_server_instance>:
        <property_name>: <property_value>

For example:

.. code-block:: yaml

  ska-tango-devices:
    spshw:
      tile-s8-1-tpm-01:
        expose: false
        devices:
          MccsTile:
          - low-mccs/tile/s8-1-tpm01
      spsstation-s8-1:
        extraVolumes:
        - name: daq-data
          persistentVolumeClaim:
            claimName: daq-data
        extraVolumeMounts:
          - name: daq-data
            mountPath: /product
        devices:
          SpsStation:
          - low-mccs/spsstation/s8-1

The device server type `spshw` is already defined by the `ska-low-mccs-spshw` chart,
and it is the only device server type available;
so all your device instances should sit under this.

Most of the keys that specify a device server instance are optional,
but one is mandatory:
the `devices` key specifies the devices to be run by the device server instance,
and is a list of device TRLs, grouped by device class.
These device TRLs must refer to an entry in the `devices` key.
That is, first we specify the devices that we want under the `device` key,
and then we allocate those devices to device servers under the `deviceServers` key.

It is possible to add device server types, or modify the existing one,
via the `deviceServerTypes` key,
but this should not normally be done.
If it should be necessary to do so,
that indicates a problem with the `ska-low-mccs-spshw` chart
that should be fixed.
