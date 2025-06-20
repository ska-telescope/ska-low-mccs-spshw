=================================
SpsStation StartBeamformer schema
=================================

Schema for SpsStation's StartBeamformer command

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

* **subarray_beam_id** (integer): Subarray beam ID of the changes to be started. Minimum: -1.

* **scan_id** (integer): The unique ID for the started scan. Minimum: 0.

