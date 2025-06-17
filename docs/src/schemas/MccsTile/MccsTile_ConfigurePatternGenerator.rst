======================================
MccsTile ConfigureTestGenerator schema
======================================

Schema for MccsTile's ConfigureTestGenerator command

**********
Properties
**********

* **stage** (string): The stage in the signal chain where the pattern is injected. Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer), or 'beamf' (output of tile beamformer). Must be one of: ["jesd", "channel", "beamf"].

* **pattern**: The data pattern in time order. It must be an array of length 1 to 1024. Length must be between 1 and 1024 (inclusive).

  * **Items** (number)

* **adders** (array): A list of length 32 that expands the pattern to cover 16 antennas and 2 polarizations in hardware. Length must be equal to 32.

  * **Items** (integer)

* **start** (boolean): Boolean flag indicating whether to start the pattern immediately. If False, the pattern will need to be started manually later.

* **shift** (integer): Optional bit shift (divides by 2^shift). This must not be used in the 'beamf' stage, where it is always overridden to 4. Minimum: 0.

* **zero** (integer): An integer (0-65535) used as a mask to disable the pattern on specific antennas and polarizations. The same mask is applied to both FPGAs, so it supports up to 8 antennas and 2 polarizations. Minimum: 0. Maximum: 65535.

