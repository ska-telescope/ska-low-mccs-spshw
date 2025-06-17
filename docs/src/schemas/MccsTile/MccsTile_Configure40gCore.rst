================================
MccsTile Configure40gCore schema
================================

Schema for MccsTile's Configure40gCore command

**********
Properties
**********

* **core_id** (integer): Core ID.

* **arp_table_entry** (integer): ARP table entry.

* **source_mac** (integer): Source MAC address.

* **source_ip** (string, format: ipv4): Source IP address.

* **source_port** (integer): Source port. Minimum: 1.

* **destination_ip** (string, format: ipv4): Destinate IP address.

* **destination_port** (integer): Destination port. Minimum: 1.

* **rx_port_filter** (integer): Receive ports filter. Minimum: 1.

* **netmask** (integer): Integer netmask for the 40g (science data) subnet. Minimum: 0. Maximum: 4294967296.

* **gateway_ip**: Integer IP address of the 40g (science data) subnet gateway. Minimum: 0. Maximum: 4294967296.

