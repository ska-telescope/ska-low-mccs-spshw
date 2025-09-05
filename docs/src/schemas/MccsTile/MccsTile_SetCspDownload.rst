==============================
MccsTile SetCspDownload schema
==============================

Schema for MccsTile's SetCspDownload command

**********
Properties
**********

* **src_port** (integer): Source port fpr data streams. Minimum: 0.

* **dst_ip_1** (string, format: ipv4): Destination IP address FPGA1.

* **dst_ip_2** (string, format: ipv4): Destination IP address FPGA2.

* **dst_port** (integer): Destination port for data streams. Minimum: 0.

* **is_last** (boolean): True for last tile in beamforming chain.

* **netmask** (string, format: ipv4): Integer netmask for the 40g (science data) subnet.

* **gateway** (string, format: ipv4): Integer IP address of the 40g (science data) subnet gateway.

