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
The Tile object is actually a factory, which returns either a Tile12 or
a Tile16 object, depending on the Tango property *TpmVersion*. 

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

Tile Polling Overview
=====================
The TileRequestProvider will determine the next item to poll on hardware.
given a 'TpmStatus' it will return a requests to execute on a poll.
see https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/reference/tile_poll_management.html
Any command will take priority over passive polling. To see the attributes Polled for each 
TpmStatus see https://developer.skao.int/projects/ska-low-mccs-spshw/en/latest/api/tile/tile_poll_management.html#ska_low_mccs_spshw.tile.tile_poll_management.initialised_tpm_read_request_iterator
    