========================================
MccsTile SetTemperatureThresholds schema
========================================

Schema for MccsTile's SetTemperatureThresholds command

**********
Properties
**********

* **board_temperature_threshold** (array): Length must be equal to 2.

  * **Items** (number): Minimum: 20. Maximum: 50.

* **fpga1_temperature_threshold** (array): Length must be equal to 2.

  * **Items** (number): Minimum: 20. Maximum: 50.

* **fpga2_temperature_threshold** (array): Length must be equal to 2.

  * **Items** (number): Minimum: 20. Maximum: 50.

