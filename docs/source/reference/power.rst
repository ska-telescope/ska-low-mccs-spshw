##########################
 Power management in MCCS
##########################

**********************
 Hardware power modes
**********************

SKA hardware may support up to three power modes:

-  on: the hardware is powered on and fully operational. This mode is
   supported by all SKA hardware.

-  off: the hardware is powered off. Generally we would expect all
   hardware to be able to be turned off. There may be special cases,
   however, where this is not supported. For example, an externally
   managed cluster can be turned off, but the MCCS interface to it might
   only allow for submission and monitoring of jobs. Thus it cannot be
   turned off from the MCCS point of view.

-  standby: the hardware is in a low-power standby mode. Such a mode is
   important in cases where powering up a device from off could take a
   long time (perhaps several minutes). Such devices may instead be
   powered up into standby mode, in which power consumption is low, but
   the time to fully power on the hardware is short (a couple of
   seconds). Standby mode is not supported by all hardware; indeed there
   may be very few hardware devices that support it.

************
 Power flow
************

The activity diagram below shows the flow of power through the MCCS
system; i.e. cabling, essentially. The (/) points are switch points at
which the power can be turned on/off. These switch points are annotated
with the Tango device commands that drive the switch.

.. uml:: power_flow.uml

*******************
 Power on sequence
*******************

Boot-up
=======

When power is first applied to MCCS, the following minimal bootup
sequence is followed:

#. Power is applied to all cabinets. All the cabinet management boards are on, 
   as they are the primary control points for the cabinet subsystems. Switches and
   subelements for the SPS cabinets are configured to remain off, as are the 
   subelements for all but one of the MCCS cabinets. 

#. Power is applied to the APIU in the field nodes. All the antennas are configured 
   to remain off. 

#. The cabinet management board for the MCCS cabinet that houses the
   MCCS controller node is configured to start up the cabinet's 1Gb
   network switch and the MCCS controller node.

#. The 1Gb network switch powers up

#. The MCCS controller node boots up.

#. The kubernetes cluster is started.

#. A minimum chart is deployed, containing just the tango subsystem and
   the MCCS Controller Tango device.

Power-on
========

When TM sends the MCCS Controller the Startup command, the MCCS
Controller must start up:

#. the rest of MCCS 
#. the SPS subrack management boards and switches
#. the SPS TPMs 
#. the field equipment

Prototype status
================

In the current prototype implementation, all of MCCS is deployed
immediately on startup, so that when TM sends the MCCS Controller the
Startup command, it need only start up the SPS cabinets and field
equipment.

.. uml:: power_sequence.uml
