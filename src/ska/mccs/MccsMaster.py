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

# PyTango imports
import tango
from tango import DebugIt
from tango.server import run
from tango.server import Device, DeviceMeta
from tango.server import attribute, command
from tango.server import device_property
from tango import AttrQuality, DispLevel, DevState
from tango import AttrWriteType, PipeWriteType
# Additional import
# PROTECTED REGION ID(MccsMaster.additionnal_import) ENABLED START #
from tango import DevEnum
from ska.base import SKAMaster
# from ska.base.control_model import (AdminMode, ControlMode, HealthState,
#                                    SimulationMode, TestMode)
from . import release
# PROTECTED REGION END #    //  MccsMaster.additionnal_import

__all__ = ["MccsMaster", "main"]


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
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(MccsMaster.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsMaster.class_variable

    # -----------------
    # Device Properties
    # -----------------

    MccsSubarrays = device_property(
        dtype='DevVarStringArray',
    )

    MccsStations = device_property(
        dtype='DevVarStringArray',
    )

    MccsStationBeams = device_property(
        dtype='DevVarStringArray',
    )

    MccsTiles = device_property(
        dtype='DevVarStringArray',
    )

    MccsAntennas = device_property(
        dtype='DevVarStringArray',
    )

    # ----------
    # Attributes
    # ----------

    commandProgress = attribute(
        dtype='DevUShort',
        label="Command progress percentage",
        polling_period=3000,
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
        doc="Percentage progress implemented for commands that  result in state/mode transitions for a large \nnumber of components and/or are executed in stages (e.g power up, power down)",
    )

    commandDelayExpected = attribute(
        dtype='DevUShort',
        unit="s",
        doc="Amount of time it will take to prepare the requested state/mode transition ? implemented as needed.",
    )

    opState = attribute(
        dtype='DevState',
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsMaster."""
        SKAMaster.init_device(self)
        # PROTECTED REGION ID(MccsMaster.init_device) ENABLED START #
        self.set_state(DevState.ON)
        self._build_state = ", ".join(
            (release.name, release.version, release.description))
        self._version_id = release.version
        # PROTECTED REGION END #    //  MccsMaster.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsMaster.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsMaster.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsMaster.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsMaster.delete_device
    # ------------------
    # Attributes methods
    # ------------------

    def read_commandProgress(self):
        # PROTECTED REGION ID(MccsMaster.commandProgress_read) ENABLED START #
        """Return the commandProgress attribute."""
        return 0
        # PROTECTED REGION END #    //  MccsMaster.commandProgress_read

    def read_commandDelayExpected(self):
        # PROTECTED REGION ID(MccsMaster.commandDelayExpected_read) ENABLED START #
        """Return the commandDelayExpected attribute."""
        return 0
        # PROTECTED REGION END #    //  MccsMaster.commandDelayExpected_read

    def read_opState(self):
        # PROTECTED REGION ID(MccsMaster.opState_read) ENABLED START #
        """Return the opState attribute."""
        return tango.DevState.UNKNOWN
        # PROTECTED REGION END #    //  MccsMaster.opState_read

    # --------
    # Commands
    # --------

    @command(
    )
    @DebugIt()
    def On(self):
        # PROTECTED REGION ID(MccsMaster.On) ENABLED START #
        """
        Power off the MCCS system.

        :return: `None`
        """
        pass
        # PROTECTED REGION END #    //  MccsMaster.On

    def is_On_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_On_allowed) ENABLED START #
        """ Is the :meth:`On` command alllowed """
        return self.get_state() not in [DevState.ON, DevState.FAULT, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_On_allowed

    @command(
    )
    @DebugIt()
    def Off(self):
        # PROTECTED REGION ID(MccsMaster.Off) ENABLED START #
        """
        Power off the MCCS system.

        :return: None
        """
        pass
        # PROTECTED REGION END #    //  MccsMaster.Off

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def StandbyLow(self):
        # PROTECTED REGION ID(MccsMaster.StandbyLow) ENABLED START #
        """
        Transition the MCCS system to the low-power STANDBY_LOW_POWER operating state.

        :return:  DevEnum
        """
        return 0
        # PROTECTED REGION END #    //  MccsMaster.StandbyLow

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def StandbyFull(self):
        # PROTECTED REGION ID(MccsMaster.StandbyFull) ENABLED START #
        """
        standbyFull	None	N/A	DevEnum	OPERATOR	ON, STANDBY_LOW_POWER	Transition the MCCS system to the STANDBY_FULL_POWER operating state.

        :return:  DevEnum
        """
        return 0
        # PROTECTED REGION END #    //  MccsMaster.StandbyFull

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def Operate(self):
        # PROTECTED REGION ID(MccsMaster.Operate) ENABLED START #
        """
        Transit to the OPERATE operating state, ready for signal processing.

        :return:  DevEnum
        """
        return 0
        # PROTECTED REGION END #    //  MccsMaster.Operate

    def is_Operate_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_Operate_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF, DevState.FAULT, DevState.INIT, DevState.ALARM, DevState.UNKNOWN, DevState.STANDBY, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_Operate_allowed

    @command(
    )
    @DebugIt()
    def Reset(self):
        # PROTECTED REGION ID(MccsMaster.Reset) ENABLED START #
        """
        The MCCS system as a whole is reinitialised as an attempt to clear an ALARM or FAULT state.

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.Reset

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def EnableSubarray(self, argin):
        # PROTECTED REGION ID(MccsMaster.EnableSubarray) ENABLED START #
        """
        Activate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.EnableSubarray

    def is_EnableSubarray_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_EnableSubarray_allowed) ENABLED START #
        return self.get_state() not in [DevState.FAULT, DevState.UNKNOWN, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_EnableSubarray_allowed

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def DisableSubarray(self, argin):
        # PROTECTED REGION ID(MccsMaster.DisableSubarray) ENABLED START #
        """
        Deactivate an MCCS Sub-Array

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.DisableSubarray

    def is_DisableSubarray_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_DisableSubarray_allowed) ENABLED START #
        return self.get_state() not in [DevState.FAULT, DevState.UNKNOWN, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_DisableSubarray_allowed

    @command(
        dtype_in='DevString',
        doc_in="JSON-formatted string",
    )
    @DebugIt()
    def Allocate(self, argin):
        # PROTECTED REGION ID(MccsMaster.Allocate) ENABLED START #
        """

        Allocate a set of unallocated MCCS resources to a sub-array. The JSON argument specifies the overall sub-array composition in terms of which stations, tiles, and antennas should be allocated to the specified Sub-Array.

        Note: Station and Tile composition is specified on the MCCS Subarray device .

        :param argin: JSON-formatted string
        :type argin: :class:`~tango.DevLong`

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.Allocate

    def is_Allocate_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_Allocate_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF, DevState.FAULT, DevState.INIT, DevState.ALARM, DevState.UNKNOWN, DevState.STANDBY, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_Allocate_allowed

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def Release(self, argin):
        # PROTECTED REGION ID(MccsMaster.Release) ENABLED START #
        """
        Release a sub-array?s Capabilities and resources (stations, tiles, antennas), marking the resources and Capabilities as unassigned and idle.

        :param argin: Sub-Array ID
        :type argin: :class:`~tango.DevLong`

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.Release

    def is_Release_allowed(self):
        # PROTECTED REGION ID(MccsMaster.is_Release_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF, DevState.FAULT, DevState.INIT, DevState.ALARM, DevState.UNKNOWN, DevState.STANDBY, DevState.DISABLE]
        # PROTECTED REGION END #    //  MccsMaster.is_Release_allowed

    @command(
    )
    @DebugIt()
    def Maintenance(self):
        # PROTECTED REGION ID(MccsMaster.Maintenance) ENABLED START #
        """
        Transition the MCCS to a MAINTENANCE state.

        :return: None
        """
        # PROTECTED REGION END #    //  MccsMaster.Maintenance

# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsMaster module."""
    # PROTECTED REGION ID(MccsMaster.main) ENABLED START #
    return run((MccsMaster,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsMaster.main


if __name__ == '__main__':
    main()
