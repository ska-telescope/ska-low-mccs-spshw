Firmware Thresholds – Engineering Mode Attributes
=================================================

Overview
--------

Firmware thresholds are attributes which are **writeable only in EngineeringMode**, to configure
and validate firmware-level safety and operational limits for voltage, current, and temperature.

The following attributes are available:

- ``firmwareVoltageThresholds``
- ``firmwareCurrentThresholds``
- ``firmwareTemperatureThresholds``

These attributes represent the threshold values read directly from the firmware and 
become available **after connecting to the TPM** (Tile Processing Module).

Behavior and Lifecycle
----------------------

When interacting with firmware thresholds, the following operational flow applies:

1. **Writing a Threshold**

   When a threshold is written:

   - The value is first written to the **firmware**.
   - If the firmware write succeeds, the **database (DB)** is updated to reflect 
     the desired value.
   - An automatic **comparison** between the DB and firmware values is then performed.

2. **Fault Detection**

   If any mismatch between the DB and firmware values is detected, the device will 
   enter a **fault state**. The fault state ensures that configuration discrepancies 
   between stored expectations and actual firmware conditions are highlighted immediately.

Diagnosing Configuration Faults
-------------------------------

The ``faultreport`` attribute provides detailed diagnostic information for configuration 
mismatches. A typical fault report looks like this:

.. code-block:: json

   {
     "firmware_configuration_status": 
     "Configuration mismatch: [voltages.MGT_AVCC_min_alarm_threshold] DB=0.829, HW=0.828; 
      [voltages.MGT_AVCC_max_alarm_threshold] DB=0.944, HW=0.945; 
      [voltages.MGT_AVTT_min_alarm_threshold] DB=1.105, HW=1.104; 
      [voltages.MGT_AVTT_max_alarm_threshold] DB=1.25, HW=1.26"
   }

This example indicates that the database (DB) and hardware (HW) values are not identical, 
resulting in a firmware configuration fault.

Clearing Configuration Faults
-----------------------------

If you wish to **clear the database values** without performing a write to firmware, 
you can set the desired thresholds to ``"Undefined"``. This is a special keyword that 
instructs the system **not to compare** firmware values for these entries.

Example:

.. code-block:: python

   tile.firmwareVoltageThresholds = json.dumps({
       "MGT_AVCC_min_alarm_threshold": "Undefined",
       "MGT_AVCC_max_alarm_threshold": "Undefined",
       "MGT_AVTT_min_alarm_threshold": "Undefined",
       "MGT_AVTT_max_alarm_threshold": "Undefined"
   })

After applying this, any mismatch faults related to these thresholds will be cleared.

Persistence and Power Cycle Behavior
------------------------------------

- **Database Persistence**

  The database values are **persisted** and **restored on startup**. A pod bounce or 
  device restart will not alter previously written threshold values.

- **Firmware Reset on Power Cycle**

  A **power cycle** resets all firmware thresholds to **default BIOS-defined values**.  
  If the database contains overridden thresholds, this will result in a 
  **configuration mismatch fault** upon reconnect.

  To resolve this:

  - Reapply the desired threshold overrides, **or**
  - Set the thresholds to ``"Undefined"`` to prevent comparison until the configuration is updated.
