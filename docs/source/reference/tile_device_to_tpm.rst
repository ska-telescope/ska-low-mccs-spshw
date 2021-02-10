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
You can swicth between simulation and real TPM driver by writing to the Tile device's
simulation_mode attribute. This will reset the Tile's TPM object.

TPM Simulator Construction
==========================
.. image:: tile_construction.svg

TPM Driver Construction
=======================
.. image:: tile_construction_driver.svg

***************************************
 Connection to TPM & Firmware Download
***************************************

The firmware download is available via a command to the Tile Tango device.
A path and name of a Vivado bit file are passed via the Tile's 'DownloadFirmware' command to the TPM.
The code checks that the file exists and then passes this file path down to the hardware
(either real or simulated).

Ursula's Sequence Diagram
=========================
.. image:: spo_943_sequence_1.svg

Gianni's Code (Modified to hook into Ursula's sequence)
=======================================================
.. image:: spo_943_sequence_2.svg

Notes
-----
* Station devices holds Vivado firmware bitfile name

* Tile devices hold specific information about the TPM's IP address

* DownloadFirmware() call will be asynchronous as programming takes several seconds

    - For the demo, does the Tango Tile device need to spin while it waits for programming completion?

    - Or, could we keep this a synchronous call and the MCCS objects will just wait for command completion?

* It doesn't look like TPM initialise is called

* After this sequence has finished, the Tile WebJive pages can be queried to return values read from the TPM hardware

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
