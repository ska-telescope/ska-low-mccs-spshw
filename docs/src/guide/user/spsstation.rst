=======================
SpsStation Tango Device
=======================

The ``SpsStation`` Tango device orchestrates a number of Tango devices that make up a station's SPS hardware.


.. uml:: device_interactions.uml


Typically, an ``SpsStation`` is responsible for 2 subracks, and 16 TPMs. This is the standard
configuration for a station: each TPM has 32 ADC channels, covering the X and Y polarisations of 16 antennas,
so a station with 16 TPMs has 512 ADC channels in total, i.e. a full 256-antenna
station. This is the typical configuration, but the ``SpsStation`` device can be configured to manage any number
of subracks and TPMs, which is useful for testing in hardware facilities such as the ITF or RAL.

It is worth familiarising yourself with the physical SPS cabinet to 
understand how the Tango Devices map to physical topology.

To understand an ``SpsStation``'s ability to operate, we can use its ``healthState`` and ``healthReport``
attributes (see ``HealthState`` (https://developer.skao.int/projects/ska-control-model/en/0.3.4/health_state.html)).
The health of the SpsStation is illustrated, in simplified form, in the diagrams below:


.. image:: images/sps_station_rollup_failed.png
   :width: 1000pt

|

.. image:: images/sps_station_rollup_degraded.png
   :width: 1000pt


Although potentially beyond the scope of this document, the following image gives some insight into how the
``HealthRollup`` class is used.


.. image:: images/sps_station_rollup.png
   :width: 1000pt

This can help you interpret the reports you can get from the SpsStation device's ``healthReport``, and how to
trace them back to the underlying inputs causing the issue.

Example ``healthReport``
-------------------------

The report only contains the entries that are not OK, and it reports each health state by name. For a station
configured with 2 subracks and 4 tiles, with everything healthy, ``healthReport`` is therefore empty:

.. code-block:: json

   {}

If ``low-mccs/tile/s8-1-tpm02`` alone reported ``DEGRADED``, ``healthReport`` would look like:

.. code-block:: json

   {
     "tiles": {
       "low-mccs/tile/s8-1-tpm02": "DEGRADED"
     }
   }

There is one entry per named rollup member that is not OK. ``subracks`` and ``tiles`` are themselves
dictionaries with one entry per unhealthy device, matching the ``k-of-n voting gate`` boxes in the diagrams
above. A member is omitted if its health is OK, and a group such as ``tiles`` is omitted if every one of its
devices is OK.

In that example the overall ``healthState`` would still be ``OK``, because the ``tiles`` threshold of
``(1, 1, 2)`` shown in the diagrams above means a single degraded tile is not enough to degrade the whole
station. A second degraded tile is needed for that.

Drilling down
-------------
If a specific Tile or Subrack is reporting ``DEGRADED`` or ``FAILED``, you should then 
check the ``HealthState`` and ``healthReport`` attributes of the offending device. 
This may already be presented in a dashboard, but if not, 
you can read the attribues directly from the device using the Tango Device API.
(https://tango-controls.readthedocs.io/projects/pytango/en/v10.3.1/tutorial/servers.html).
