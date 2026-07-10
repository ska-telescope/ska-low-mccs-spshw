
=================
Subrack Simulator
=================

Health Status Payload
=====================

The simulator health payload reflects live simulator PSU telemetry. In
particular, PSU ``voltage_out`` and ``power_out`` values in ``health_status`` are
derived from current ``power_supply_voltages`` and ``power_supply_currents``.

This allows health-driven attributes such as ``psuDeadCount`` to respond to
runtime simulator attribute changes used in tests and debugging.

.. automodule:: ska_low_mccs_spshw.subrack.subrack_simulator
   :members:
