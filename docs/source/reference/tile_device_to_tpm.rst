###################
 Tango Tile to TPM
###################

********************************
 Tango Tile Device Construction
********************************

The TPM (or simulator) is created during the Tile's Init command.
This command is executed automatically during construction of the Tile Tango device.
The decision whether to use the TPM simulator or a real hardware driver is made
with the simulation_mode flag. This is currently hardcoded to SimulationMode.TRUE
in tile_device.py. This means that either the TPM simulator or the real hardware
driver is available as soon as the Tile Tango device is ready for use.

.. uml:: tile_construction.uml

*******************
 Connection to TPM
*******************

There is missing implementation in hardware.py, class HardwareDriver to determine
whether we are connected to real hardware. This currently raises a 'NotImplementedError' exception.

WIP: Which of these attributes is required so we can make a connection to a TPM?
Ask for Gianni's input here.

- TileIP - Seems an obvious requirement so we can address the specific TPM hardware
- TpmCpldPort - The TPM has a CPLD that is used for programming the firmware. It is rarely updated.
- LmcIp - What is this used for?
- DstPort - What is this used for?

Ursula's Sequence Diagram
=========================
.. uml:: spo_943_sequence_1.uml

Ross' Proposal
==============
.. uml:: spo_943_sequence_2.uml

Notes
-----
* Station devices holds filepath of firmware Vivado bitfile

* Tile devices hold specific information about the TPM's IP address

* DownloadFirmware() call will be asynchronous as programming takes several seconds

    - For the demo, the Tango device will be made to spin while it waits for programming completion

* What does the call to TPM Driver Initialise() do?

* After this sequence has finished, the Tile WebJive pages can be queried to return values read from the TPM hardware

*******************
 Firmware Download
*******************

The firmware download is available via a command to the Tile Tango device.
A path and name of a Vivado bit file are passed via the Tile's 'DownloadFirmware' command to the TPM.
The code checks that the file exists and then passes this file path down to the hardware
(either real or simulated).

.. uml:: tile_program_firmware.uml

***********************
 Tile Power Management
***********************

The system is considered to be in a low power mode until the TPM firmware has been loaded and
is running. The whole topic of power management is an evolving area with conversations being
had between Gianni, Mark and Alan...It involves the subrack, network switches as well as the
TPM itself. For feature SPO-943, we will need to determine the initial state with respect to power
and power mode. These initial conditions are also being flushed out by Daniel Hayden. It's
likely the initial conditions will involve a manual setup to ensure the TPM is powered and in
a state that the Tile Tango device can communicate with it.
