# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MccsMaster Tango device prototype

MccsMaster TANGO device class for the MccsMaster prototype
"""
__all__ = ["MccsMaster", "main"]

# PyTango imports
import tango
from tango import DebugIt
from tango.server import attribute, command
from tango.server import device_property
from tango import DevState

# Additional import
# from tango import DevEnum
from ska.base import SKAMaster

# from ska.base.control_model import (AdminMode, ControlMode, HealthState,
#                                    SimulationMode, TestMode)
import ska.mccs.release as release


class MccsMaster(SKAMaster):
    """
    MccsMaster TANGO device class for the MccsMaster prototype

    **Properties:**

    - Device Property
        MccsSubarrays
            - The FQDNs of the Mccs sub-arrays
            - Type: :class:`~tango.DevVarStringArray`
        MccsStations
            - List of MCCS station  TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsStationBeams
            - List of MCCS station beam TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsTiles
            - List of MCCS Tile TANGO Device names.
            - Type: :class:`~tango.DevVarStringArray`
        MccsAntennas
            - List of MCCS Antenna TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
    """

    # -----------------
    # Device Properties
    # -----------------

    MccsSubarrays = device_property(dtype="DevVarStringArray",)

    MccsStations = device_property(dtype="DevVarStringArray",)

    MccsStationBeams = device_property(dtype="DevVarStringArray",)

    MccsTiles = device_property(dtype="DevVarStringArray",)

    MccsAntennas = device_property(dtype="DevVarStringArray",)

    # ----------
    # Attributes
    # ----------

    commandProgress = attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        polling_period=3000,
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
        doc="Percentage progress implemented for commands that result in "
        "state/mode transitions for a large \nnumber of components and/or "
        "are executed in stages (e.g power up, power down)",
    )

    commandDelayExpected = attribute(
        dtype="DevUShort",
        unit="s",
        doc="Amount of time it will take to prepare the requested state/mode "
        "transition ? implemented as needed.",
    )

    opState = attribute(dtype="DevState",)

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsMaster."""
        SKAMaster.init_device(self)

        self.set_state(DevState.ON)
        self._build_state = release.get_release_info()
        self._version_id = release.version

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ------------------
    # Attributes methods
    # ------------------

    def read_commandProgress(self):

        """Return the commandProgress attribute."""
        return 0

    def read_commandDelayExpected(self):

        """Return the commandDelayExpected attribute."""
        return 0

    def read_opState(self):

        """Return the opState attribute."""
        return tango.DevState.UNKNOWN

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def On(self):

        """
        Power off the MCCS system.

        :return: `None`
        """
        pass

    def is_On_allowed(self):

        """ Is the :meth:`On` command alllowed """
        allowed = [DevState.ON, DevState.FAULT, DevState.DISABLE]
        return self.get_state() not in allowed

    @command()
    @DebugIt()
    def Off(self):

        """
        Power off the MCCS system.

        :return: None
        """
        pass

    @command(dtype_out="DevEnum",)
    @DebugIt()
    def StandbyLow(self):

        """
        Transition the MCCS system to the low-power STANDBY_LOW_POWER
        operating state.

        :return:  DevEnum
        """
        return 0

    @command(dtype_out="DevEnum",)
    @DebugIt()
    def StandbyFull(self):

        """
        standbyFull	None	N/A	DevEnum	OPERATOR	ON, STANDBY_LOW_POWER
        Transition the MCCS system to the STANDBY_FULL_POWER operating state.

        :return:  DevEnum
        """
        return 0

    @command(dtype_out="DevEnum",)
    @DebugIt()
    def Operate(self):

        """
        Transit to the OPERATE operating state, ready for signal processing.

        :return:  DevEnum
        """
        return 0

    def is_Operate_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command()
    @DebugIt()
    def Reset(self):

        """
        The MCCS system as a whole is reinitialised as an attempt to clear
        an ALARM or FAULT state.

        :return: None
        """

    @command(
        dtype_in="DevLong", doc_in="Sub-Array ID",
    )
    @DebugIt()
    def EnableSubarray(self, argin):

        """
        Activate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """

    def is_EnableSubarray_allowed(self):

        return self.get_state() not in [
            DevState.FAULT,
            DevState.UNKNOWN,
            DevState.DISABLE,
        ]

    @command(
        dtype_in="DevLong", doc_in="Sub-Array ID",
    )
    @DebugIt()
    def DisableSubarray(self, argin):

        """
        Deactivate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """

    def is_DisableSubarray_allowed(self):

        return self.get_state() not in [
            DevState.FAULT,
            DevState.UNKNOWN,
            DevState.DISABLE,
        ]

    @command(
        dtype_in="DevString", doc_in="JSON-formatted string",
    )
    @DebugIt()
    def Allocate(self, argin):

        """

        Allocate a set of unallocated MCCS resources to a sub-array.
        The JSON argument specifies the overall sub-array composition in
        terms of which stations, tiles, and antennas should be allocated
        to the specified Sub-Array.

        Note: Station and Tile composition is specified on the MCCS
        Subarray device .

        :param argin: JSON-formatted string
        :type argin: :class:`~tango.DevLong`

        :return: None
        """
        print("Command Allocate", argin)

    def is_Allocate_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command(
        dtype_in="DevLong", doc_in="Sub-Array ID",
    )
    @DebugIt()
    def Release(self, argin):

        """
        Release a sub-array?s Capabilities and resources (stations, tiles,
        antennas), marking the resources and Capabilities as unassigned and
        idle.

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """

    def is_Release_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command()
    @DebugIt()
    def Maintenance(self):

        """
        Transition the MCCS to a MAINTENANCE state.

        :return: None
        """


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsMaster module."""

    return MccsMaster.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
