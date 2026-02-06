===============================
MccsTile StartBeamformer schema
===============================

Schema for MccsTile's StartBeamformer command

**********
Properties
**********

* **start_time**: .

  **One of**
    * string, format: time

    * null

* **duration**: Duration in CSP frames (or -1 to run forever).

  **One of**
    * integer: Minimum: -1.

    * null

* **channel_groups**: Channel groups to be started.

  **One of**
    * array: Length must be between 0 and 48 (inclusive).

      * **Items** (integer): Minimum: 0. Maximum: 47.

    * null

* **scan_id** (integer): The unique ID for the started scan. Minimum: 0.

