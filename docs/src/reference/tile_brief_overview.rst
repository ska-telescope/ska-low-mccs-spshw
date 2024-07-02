##########################
 MccsTile general overview
##########################

This page gives a general brief overview to the architecture of the MccsTile.

********************************
 Tango Tile Device Construction
********************************

During deployment MccsTile is constructed with a platform specific configuration defined by helm see https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/guide/deploy.html.
The MccsTile contructs a TileComponentManager using information from this configuration. 
This configuration includes a simulation_mode flag. When simulation_mode is TRUE a TileSimulator 
will be constructed and used as the backend, when False a pyaavs.Tile object will be created to 
interface with the hardware as a backend.

Tile brief architecture
=======================
The MccsTile inherits from the SkaTangoBase class, this is the interface for TANGO control.
Information and instructions are sent to the hardware using this interface via a 'TileComponentManager'. 
The 'TileComponentManager' is a 'PollingComponentManager' and will poll requests on the backend system, 
the decision of what to poll is determined by the 'TileRequestProvider'. 

.. uml:: tile_class_diagram_brief.uml

Tile On sequence
================
The "On" command will bring the MccsTile to 'PowerState.ON https://developer.skao.int/projects/ska-control-model/en/latest/power_state.html
This will involve sending athe On command to the MccsSubrack to deliver power then executing the initialise
command to the TPM as soon as it is connectable.

.. uml:: tile_on.uml

For more information about how the Tile On command fits into the power sequence 
see https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/reference/power.html

Tile operation state
====================
See https://developer.skao.int/projects/ska-control-model/en/stable/op_state.html.

Information specific to Tile is provided below:

-  UNKNOWN: the control system is monitoring (or at least trying to monitor) the system under control, but is unable to determine its state.
   this will occur when we cannot connect with the TPM and the MccsSubrack is reporting its ports power UNKNOWN.

-  OFF: the control system is monitoring the system under control, which is powered off. This will occur when MccsSubrack says the port
   is NO_SUPPLY or OFF, and we are NOT connected with the TPM.

-  STANDBY: Not implemented in Tile.

-  ON: The control system is monitoring the system under control, which is turned on.
   This will occur when we are connected and communicating with the TPM.

-  FAULT: The Tile will be in state FAULT under inconsistent state. Currently if we can connect with the TPM but the MccsSubrack is reporting 
   a inconsistent state (i.e not ON), we are in FAULT state.

Tile Polling Overview
=====================
The TileRequestProvider will determine the next item to poll on hardware.
given a 'TpmStatus' it will return a requests to execute on a poll.

Commands will take priority over passive monitoring requests.
    