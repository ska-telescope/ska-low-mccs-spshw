==============================
MccsTile SetLmcDownload schema
==============================

Schema for MccsTile's SetLmcDownload command

**********
Properties
**********

* **mode** (string): Mode: 1G or 10G. Must be one of: ["1g", "1G", "10g", "10G"].

* **payload_length** (integer): SPEAD payload length for channel data. Minimum: 0.

* **destination_ip** (string, format: ipv4): Destination IP address.

* **source_port** (integer): Source port for integrated data streams. Minimum: 0.

* **destination_port** (integer): Destination port for integrated data streams. Minimum: 0.

* **netmask_40g** (integer): Integer netmask for the 40g (science data) subnet. Minimum: 0. Maximum: 4294967296.

* **gateway_40g**: Integer IP address of the 40g (science data) subnet gateway. Minimum: 0. Maximum: 4294967296.

