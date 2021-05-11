##########################
Subrack device to hardware
##########################

The subrack Tango device controls a subrack management board (SMB), which in turn monitors and controls a SPS subrack. This turns on and off individual TPM boards, monitors TPM supply voltages, currents and temperatures, and manages cooling fans.

The SMB is controlled by a ARM microcontroller and a standalone program. The subrack Tango device operates in the MCCS cluster, and communicates with the microcontroller to execute Tango functions. 

The subrack has 8 bays, numbered from 1 to 8, which host up to 8 TMB. All attributes related to bays (TMB) return a tuple of 8 elements, with element 0 corresponding to bay 1. Use of 1-based indexes for bays has been chosen to be more understandable by a human operator.

*****************************
Remote hardware web interface
*****************************

The subrack device communicates with the actual hardware using a web based interface. The interface is implemented by the WebHardwareClient, with the protocol implemented by the HardwareClient class.

This class interfaces with a remote hardware. It has 4 main methods: 
* connect() checks the connection status or reopens it. It returns True if the connection can be established.
* get_attribute(attributeName) retrieves the current value of a hardware attribute
* set_attribute(attributeName, value) sets the current value of a hardware attribute
* execute_command(commandName, parameters) executes a command on the hardware, with the provided optional parameters

The attribute and command methods return a dictionary, with the return value and status.

Attributes are retrieved instantly (in less than 1 second) and are synchronous. Commands may be synchronous (short execution time) or asynchronous, if they require a longer time to execute. Each command is defined to be always synchronous 
or asynchronous. Asynchronous commands block the hardware until completion, i.e. all further requests are denied. Special commands are used to check for command completion or to abort it.

Attribute query example
=======================

.. uml:: subrack_attribute.uml

An attribute read operation translates to a specific method in the SubrackDriver object, which queries the WebHardwareClient object. It sends a html query to the subrack management board, which replies with a json formatted dictionary. The dictionary contains the returned value (scalar or list) which is translated to the required attribute value by the Tango device. 

Power on a TPM
==============
.. uml:: subrack_command.uml

A command to power on a TPM is more complex. The command is not completed instantaneously, so the driver polls every second whether the command has completed. When this happens, the Tango device queries the TPM On status, and if a change is
detected, generates an event. The Tile devices subscribe to this event, in order to change their status accordingly. 
