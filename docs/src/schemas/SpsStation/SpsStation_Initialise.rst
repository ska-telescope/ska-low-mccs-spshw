============================
SpsStation Initialise schema
============================

Schema for SpsStations's Initialise command

**********
Properties
**********

* **global_reference_time** (string): Common global reference time for all TPMs, needs to be some time in the last 2 weeks. If not provided, 8am on the most recent Monday AWST will be used.

* **start_bandpasses** (boolean): Whether to configure the TPMs to send integrated channel data to the bandpass DAQ.

