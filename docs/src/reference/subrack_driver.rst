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

*******************************
Upstream communication handling
*******************************

The subrack device also connects to upstream devices (the PDU and the
PowerMarshaller). Their connection status is combined with the status of the
connection to the subrack itself (SMB) to give the device's communication
status. While any upstream connection is not ``ESTABLISHED``, the device is in
``UNKNOWN`` state, because accurate power state information is unavailable.

Note that the subrack driver polls only the subrack. The upstream devices are
not polled: their connection status changes when the device connects to them,
when communication is started or stopped (for example by changing ``adminMode``),
and when a connection attempt is retried. Hardware polling continues
independently of upstream connections.

Recovery from UNKNOWN
=====================

The device only leaves ``UNKNOWN`` when it receives a power state update, but
the driver does not re-publish a value that has not changed. If upstream
communication is (re-)established while the subrack has been polled
successfully and is ``ON`` throughout, no new power update would arrive, and
the device would stay in ``UNKNOWN`` until it was re-initialised.

To avoid this, when all upstream connections and the subrack connection are
``ESTABLISHED``, the component manager re-asserts the driver's last known power
state (``ON``). If the driver has no known power state, or the subrack
connection is not established, nothing is re-asserted.

Fault updates
=============

Fault updates are only valid in the ``ON`` and ``STANDBY`` operating states, so
applying one while the device is ``UNKNOWN`` or ``OFF`` would be an illegal
state transition. A fault update received at such a time is held, and applied
by the next component state update after the device reaches a state in which it
is legal. A later fault update replaces a held one. When the device goes
``OFF`` any held fault is discarded, as a device that is off cannot be faulty.

PSU Dead Count And Health Events
================================

The ``psuDeadCount`` attribute is derived from Subrack health telemetry, not from
an immediate direct read of PSU voltage attributes.

When health is evaluated from attributes (``UseAttributesForHealth=True``):

* ``psuDeadCount`` is computed from the ``health_status`` payload.
* Updates follow the health command polling cadence controlled by
	``CommandUpdateRate``.
* The change event for ``psuDeadCount`` is configured without Tango value
	filtering, so transitions such as initial INVALID to 0 and recovery 1 to 0 are
	published as change events.

Current health/state behaviour for PSU failures is:

* 0 dead PSUs: health is ``OK``.
* 1 dead PSU: health is ``DEGRADED`` and device state is ``ALARM``.
* 2 dead PSUs: health is ``FAILED`` and device state is ``ALARM``.

For tests and troubleshooting where immediate refresh is needed, call
``UpdateHealthAttributes`` rather than waiting for the next
``CommandUpdateRate`` cycle.
