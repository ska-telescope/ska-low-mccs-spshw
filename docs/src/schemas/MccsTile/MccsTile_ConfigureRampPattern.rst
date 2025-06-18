====================================
MccsTile ConfigureRampPattern schema
====================================

Schema for MccsTile's ConfigureRampPattern command

**********
Properties
**********

* **stage** (string): The stage in the signal chain where the pattern is injected. Options are: 'jesd' (output of ADCs), 'channel' (output of channelizer), or 'beamf' (output of tile beamformer). Must be one of: ["jesd", "channel", "beamf", "all"].

* **polarisation**: The polarisation to apply the ramp for. This must be 0, 1 or -1 to use all stages. Minimum: -1. Maximum: 1.

  * **Items** (integer)

* **ramp** (string): The ramp to use. Options are 'ramp1', 'ramp2' or 'all' to use all ramps. (note: ramp2 = ramp1 + 1234). Must be one of: ["ramp1", "ramp2", "all"].

