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

To deploy ``ska-low-mccs-spshw`` onto a k8s cluster, use the command
``helmfile --environment <environment_name> sync``.
To see what environments are supported,
see the ``environments`` section of ``helmfile.d/helmfile.yaml``.

(Although helmfile supports k8s context switching, this has not yet
been set up. You must manually set your k8s context for the platform
you are targetting, before running the above command.)

To tear down a release that has been deployed by helmfile,
use the command ``helmfile destroy`` or ``helmfile --environment <environment_name> delete``.

------------
How it works
------------
The ``environments`` section of ``helmfile.d/helmfile.yaml`` specifies
a sequence of helmfile values files for each environment.
The first file will generally be a specification of the target platform.
This file should only change when the platform itself changes.

For example, the platform specification for PSI-Low,
which currently has one subrack and two TPMs, is:

.. code-block:: yaml

   platform:
     metadata:
       version: 0.0.3
       description: A platform configuration specification for the PSI-Low.
     cluster:
       domain: cluster.local
     array:
       name: psi-low
       stations:
         "1":
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
         stations:
           "1":
             sps:
               tpms:
                 "10":
                   logging_level_default: 5

  Two special keys are supported:

  * The ``enabled`` key can be applied to any device instance,
    to enable or disable deployment of that device.
    For example, to disable deployment of the devices
    that support station calibration:

    .. code-block:: yaml

       overrides:
         array:
           stations:
             "1":
               sps:
                 calibration_store:
                   enabled: false
                 mock_field_station:
                   enabled: false
                 station_calibrator:
                   enabled: false

    One can also disable an entire station, and then enable only certain
    devices:

    .. code-block:: yaml

       overrides:
         array:
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
    or should simulate their interactions between hardware.
    Not all device templates support this key,
    and those that do may handle it in different ways.
    For example the subrack device template deploys a subrack simulator
    for it to monitor and control, whereas the TPM device template
    merely puts the TPM device into simulation mode.

    For example:

    .. code-block:: yaml

       overrides:
         array:
           stations:
             "1":
               enabled: false
               sps:
                 subracks:
                   "1":
                     simulated: true

--------------------------------
Direct deployment of helm charts
--------------------------------
It is possible to deploy helm charts directly.
However note that helm chart configuration is handled by helmfile,
so the helm chart values files are expected to provide
a deterministic, fully-configured specification
of what devices and simulators should be deployed.
For example:

.. code-block:: yaml

   deviceServers:
     subracks:
       1:
         logging_level_default: 5
         nodeSelector:
           kubernetes.io/hostname: psi-node3
         srmb_host: subrack-simulator-1
         srmb_port: 8081
     tpms:
       10:
         host: 10.0.10.218
         logging_level_default: 5
         nodeSelector:
           kubernetes.io/hostname: psi-node3
         port: 10000
         subrack: 1
         subrack_slot: 2
         version: tpm_v1_6
   
   simulators:
     subracks:
       1:
         srmb_host: subrack-simulator-1
         srmb_port: 8081
