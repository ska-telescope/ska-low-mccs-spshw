============================
SpsStation LoadScanId schema
============================

Schema for SpsStation's LoadScanId command

**********
Properties
**********

* **channel_groups**: Channel groups to be affected.

  **One of**
    * array: Length must be between 0 and 48 (inclusive).

      * **Items** (integer): Minimum: 0. Maximum: 47.

    * null

* **scan_id** (integer): The unique ID for the scan. Minimum: 0.

