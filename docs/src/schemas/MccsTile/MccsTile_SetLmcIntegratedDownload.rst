========================================
MccsTile SetLmcIntegratedDownload schema
========================================

Schema for MccsTile's SetLmcIntegratedDownload command

**********
Properties
**********

* **mode** (string): Mode: 1G or 10G. Must be one of: ["1g", "1G", "10g", "10G"].

* **channel_payload_length** (integer): SPEAD payload length for integrated channel data. Minimum: 0.

* **beam_payload_length** (integer): SPEAD payload length for integrated beam data. Minimum: 0.

* **destination_ip** (string, format: ipv4): Destination IP address.

* **source_port** (integer): Source port for integrated data streams. Minimum: 0.

* **destination_port** (integer): Destination port for integrated data streams. Minimum: 0.

* **netmask_40g** (integer): Integer netmask for the 40g (science data) subnet. Minimum: 0. Maximum: 4294967296.

* **gateway_40g**: Integer IP address of the 40g (science data) subnet gateway. Minimum: 0. Maximum: 4294967296.

