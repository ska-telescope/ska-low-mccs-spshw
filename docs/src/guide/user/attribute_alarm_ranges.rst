======================
Attribute Alarm Ranges
======================

As part of Health monitoring in MCCS, certain attributes are set up to raise warnings and alarms when they go outside pre determined ranges. These are Health Attributes.

Attribute alarm ranges
----------------------

The thresholds of an Health Attribute can be set in 3 places: 

1. **Attribute definition** - within the tango device definition, the attribute is set up with a default value. This is overwritten during setup.
#. **Class properties** - chart-wide defaults for every device of a class, under
   ``ska-tango-devices.classProperties.<DeviceClass>`` in
   ``charts/ska-low-mccs-spshw/values.yaml``.
#. **Device properties** - per-device overrides, under
   ``ska-tango-devices.devices.<DeviceClass>.<trl>`` in the platform's helmfile values
   (e.g. ``helmfile.d/values/values-ral-2.yaml``).

Each threshold uses the ``<attribute>-><property>`` syntax, where ``<property>`` is one of ``max_alarm``, ``max_warning``, ``min_warning`` or ``min_alarm``:

.. code-block:: yaml

   classProperties:
     MccsSubrack:
       boardTemperatures->max_alarm: 50.0
       boardTemperatures->max_warning: 45.0

To disable a threshold, set it to ``"Not specified"``. Note that the value can still be stuck in the Tango Database for a few minutes before it gets updated

Thresholds can also be changed at runtime using device/attribute proxies, but these changes are lost on redeployment.

.. code-block:: python

   import tango

   subrack = tango.DeviceProxy("low-mccs/subrack/stfc-ral-2-sr2")
   config = subrack.get_attribute_config("boardTemperatures")
   config.alarms.max_alarm = "55.0"
   config.alarms.max_warning = "50.0"
   config.alarms.min_alarm = "Not specified"  # disable
   subrack.set_attribute_config(config)

Subrack Attributes
^^^^^^^^^^^^^^^^^^

Max Fan Speed
-------------

``subrackMaxFanSpeeds`` (RPM) is the estimated fan speed at 100% PWM duty, scaled from the measured fan speed and current duty cycle. 

Defaults (percentage of the nominal 6500 RPM):

=================  ========  =======
Property           RPM       Nominal
=================  ========  =======
``max_alarm``      9750      150%
``max_warning``    8125      125%
``min_warning``    4875      75%
``min_alarm``      1625      25%
=================  ========  =======

If a subrack has a known faulty fan, users can disable the minimum thresholds for that device only:

.. code-block:: yaml

   ska-tango-devices:
     devices:
       MccsSubrack:
         low-mccs/subrack/stfc-ral-2-sr2:
           subrackMaxFanSpeeds->min_warning: "Not specified"
           subrackMaxFanSpeeds->min_alarm: "Not specified"

.. note::

   Disabling these thresholds hides genuine fan failures on that subrack.