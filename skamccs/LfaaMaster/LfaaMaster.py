# -*- coding: utf-8 -*-
#
# This file is part of the LfaaMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LfaaMaster Tango device prototype

LfaaMaster TANGO device class for the LfaaMaster prototype
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
import enum
#from SKAMaster import SKAMaster
# Additional import
# PROTECTED REGION ID(LfaaMaster.additionnal_import) ENABLED START #
from skabase.SKAMaster import SKAMaster
# PROTECTED REGION END #    //  LfaaMaster.additionnal_import

__all__ = ["LfaaMaster"]


class HealthState(enum.IntEnum):
    """Python enumerated type for HealthState attribute."""


class AdminMode(enum.IntEnum):
    """Python enumerated type for AdminMode attribute."""


class ControlMode(enum.IntEnum):
    """Python enumerated type for ControlMode attribute."""


class SimulationMode(enum.IntEnum):
    """Python enumerated type for SimulationMode attribute."""


class TestMode(enum.IntEnum):
    """Python enumerated type for TestMode attribute."""


class LoggingLevel(enum.IntEnum):
    """Python enumerated type for LoggingLevel attribute."""


class LfaaMaster(SKAMaster):
    """
    LfaaMaster TANGO device class for the LfaaMaster prototype

    **Properties:**

    - Device Property
        LfaaSubarrays
            - The FQDNs of the Lfaa sub-arrays
            - Type:'DevVarStringArray'
        LfaaStations
            - List of LFAA station  TANGO Device names
            - Type:'DevVarStringArray'
        LfaaStationBeams
            - List of LFAA station beam TANGO Device names
            - Type:'DevVarStringArray'
        LfaaTiles
            - List of LFAA Tile TANGO Device names.
            - Type:'DevVarStringArray'
        LfaaAntennas
            - List of LFAA Antenna TANGO Device names
            - Type:'DevVarStringArray'
    """
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(LfaaMaster.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  LfaaMaster.class_variable

    # -----------------
    # Device Properties
    # -----------------









    LfaaSubarrays = device_property(
        dtype='DevVarStringArray',
    )



    LfaaStations = device_property(
        dtype='DevVarStringArray',
    )

    LfaaStationBeams = device_property(
        dtype='DevVarStringArray',
    )

    LfaaTiles = device_property(
        dtype='DevVarStringArray',
    )

    LfaaAntennas = device_property(
        dtype='DevVarStringArray',
    )

    # ----------
    # Attributes
    # ----------











    adminMode = attribute(
        dtype=AdminMode,
        access=AttrWriteType.READ_WRITE,
        polling_period=1000,
        memorized=True,
        doc="The admin mode reported for this device. It may interpret the current device condition \nand condition of all managed devices to set this. Most possibly an aggregate attribute.",
    )

    controlMode = attribute(
        dtype=ControlMode,
        access=AttrWriteType.READ_WRITE,
        polling_period=1000,
        memorized=True,
        doc="The control mode of the device. REMOTE, LOCAL\nTANGO Device accepts only from a �local� client and ignores commands and queries received from TM\nor any other �remote� clients. The Local clients has to release LOCAL control before REMOTE clients\ncan take control again.",
    )



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
        doc="Amount of time it will take to prepare the requested state/mode transition � implemented as needed.",
    )

    opState = attribute(
        dtype='DevState',
    )


    availableCapabilities = attribute(
        dtype=('DevString',),
        max_dim_x=20,
        doc="A list of available number of instances of each capability type, e.g. `CORRELATOR:512`, `PSS-BEAMS:4`.",
    )

    subarrayFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=16,
        doc="Array of FQDNs for the instances of the Subarray TANGO devices running with the LFAA LMC",
    )


    stationBeamFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=16,
        doc="Array of FQDNs for the instances of the station beam TANGO devices running with the LFAA LMC",
    )

    stationFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=16,
        doc="Array of FQDNs for the instances of the station TANGO devices running with the LFAA LMC",
    )

    tileFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=16,
        doc="Array of FQDNs for the instances of the tile TANGO devices running with the LFAA LMC",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the LfaaMaster."""
        SKAMaster.init_device(self)
        # PROTECTED REGION ID(LfaaMaster.init_device) ENABLED START #
        # PROTECTED REGION END #    //  LfaaMaster.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(LfaaMaster.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  LfaaMaster.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(LfaaMaster.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  LfaaMaster.delete_device
    # ------------------
    # Attributes methods
    # ------------------

    def read_adminMode(self):
        # PROTECTED REGION ID(LfaaMaster.adminMode_read) ENABLED START #
        """Return the adminMode attribute."""
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.adminMode_read

    def write_adminMode(self, value):
        # PROTECTED REGION ID(LfaaMaster.adminMode_write) ENABLED START #
        """Set the adminMode attribute."""
        pass
        # PROTECTED REGION END #    //  LfaaMaster.adminMode_write

    def read_controlMode(self):
        # PROTECTED REGION ID(LfaaMaster.controlMode_read) ENABLED START #
        """Return the controlMode attribute."""
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.controlMode_read

    def write_controlMode(self, value):
        # PROTECTED REGION ID(LfaaMaster.controlMode_write) ENABLED START #
        """Set the controlMode attribute."""
        pass
        # PROTECTED REGION END #    //  LfaaMaster.controlMode_write

    def read_commandProgress(self):
        # PROTECTED REGION ID(LfaaMaster.commandProgress_read) ENABLED START #
        """Return the commandProgress attribute."""
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.commandProgress_read

    def read_commandDelayExpected(self):
        # PROTECTED REGION ID(LfaaMaster.commandDelayExpected_read) ENABLED START #
        """Return the commandDelayExpected attribute."""
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.commandDelayExpected_read

    def read_opState(self):
        # PROTECTED REGION ID(LfaaMaster.opState_read) ENABLED START #
        """Return the opState attribute."""
        return tango.DevState.UNKNOWN
        # PROTECTED REGION END #    //  LfaaMaster.opState_read

    def read_availableCapabilities(self):
        # PROTECTED REGION ID(LfaaMaster.availableCapabilities_read) ENABLED START #
        """Return the availableCapabilities attribute."""
        return ('',)
        # PROTECTED REGION END #    //  LfaaMaster.availableCapabilities_read

    def read_subarrayFQDNs(self):
        # PROTECTED REGION ID(LfaaMaster.subarrayFQDNs_read) ENABLED START #
        """Return the subarrayFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  LfaaMaster.subarrayFQDNs_read

    def read_stationBeamFQDNs(self):
        # PROTECTED REGION ID(LfaaMaster.stationBeamFQDNs_read) ENABLED START #
        """Return the stationBeamFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  LfaaMaster.stationBeamFQDNs_read

    def read_stationFQDNs(self):
        # PROTECTED REGION ID(LfaaMaster.stationFQDNs_read) ENABLED START #
        """Return the stationFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  LfaaMaster.stationFQDNs_read

    def read_tileFQDNs(self):
        # PROTECTED REGION ID(LfaaMaster.tileFQDNs_read) ENABLED START #
        """Return the tileFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  LfaaMaster.tileFQDNs_read

    # --------
    # Commands
    # --------

    @command(
    )
    @DebugIt()
    def On(self):
        # PROTECTED REGION ID(LfaaMaster.On) ENABLED START #
        """
        Power off the LFAA system.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.On

    def is_On_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_On_allowed) ENABLED START #
        return self.get_state() not in [DevState.ON,DevState.FAULT,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_On_allowed

    @command(
    )
    @DebugIt()
    def Off(self):
        # PROTECTED REGION ID(LfaaMaster.Off) ENABLED START #
        """
        Power off the LFAA system.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.Off

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def StandbyLow(self):
        # PROTECTED REGION ID(LfaaMaster.StandbyLow) ENABLED START #
        """
        Transition the LFAA system to the low-power STANDBY_LOW_POWER operating state.

        :return:'DevEnum'
        """
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.StandbyLow

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def StandbyFull(self):
        # PROTECTED REGION ID(LfaaMaster.StandbyFull) ENABLED START #
        """
        standbyFull	None	N/A	DevEnum	OPERATOR	ON, STANDBY_LOW_POWER	Transition the LFAA system to the STANDBY_FULL_POWER operating state.

        :return:'DevEnum'
        """
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.StandbyFull

    @command(
        dtype_out='DevEnum',
    )
    @DebugIt()
    def Operate(self):
        # PROTECTED REGION ID(LfaaMaster.Operate) ENABLED START #
        """
        Transit to the OPERATE operating state, ready for signal processing.

        :return:'DevEnum'
        """
        return 0
        # PROTECTED REGION END #    //  LfaaMaster.Operate

    def is_Operate_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_Operate_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF,DevState.FAULT,DevState.INIT,DevState.ALARM,DevState.UNKNOWN,DevState.STANDBY,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_Operate_allowed

    @command(
    )
    @DebugIt()
    def Reset(self):
        # PROTECTED REGION ID(LfaaMaster.Reset) ENABLED START #
        """
        The LFAA system as a whole is reinitialised as an attempt to clear an ALARM or FAULT state.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.Reset

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def EnableSubarray(self, argin):
        # PROTECTED REGION ID(LfaaMaster.EnableSubarray) ENABLED START #
        """
        Activate an LFAA Sub-Array

        :param argin: 'DevLong'
        Sub-Array ID

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.EnableSubarray

    def is_EnableSubarray_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_EnableSubarray_allowed) ENABLED START #
        return self.get_state() not in [DevState.FAULT,DevState.UNKNOWN,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_EnableSubarray_allowed

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def DisableSubarray(self, argin):
        # PROTECTED REGION ID(LfaaMaster.DisableSubarray) ENABLED START #
        """
        Deactivate an LFAA Sub-Array

        :param argin: 'DevLong'
        Sub-Array ID

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.DisableSubarray

    def is_DisableSubarray_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_DisableSubarray_allowed) ENABLED START #
        return self.get_state() not in [DevState.FAULT,DevState.UNKNOWN,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_DisableSubarray_allowed

    @command(
        dtype_in='DevString',
        doc_in="JSON-formatted string",
    )
    @DebugIt()
    def Allocate(self, argin):
        # PROTECTED REGION ID(LfaaMaster.Allocate) ENABLED START #
        """
        
            Allocate a set of unallocated LFAA resources to a sub-array. The JSON argument specifies the overall sub-array composition in terms of which stations, tiles, and antennas should be allocated to the specified Sub-Array. 
            Note: Station and Tile composition is specified on the LFAA Subarray device .

        :param argin: 'DevString'
        JSON-formatted string

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.Allocate

    def is_Allocate_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_Allocate_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF,DevState.FAULT,DevState.INIT,DevState.ALARM,DevState.UNKNOWN,DevState.STANDBY,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_Allocate_allowed

    @command(
        dtype_in='DevLong',
        doc_in="Sub-Array ID",
    )
    @DebugIt()
    def Release(self, argin):
        # PROTECTED REGION ID(LfaaMaster.Release) ENABLED START #
        """
        Release a sub-array?s Capabilities and resources (stations, tiles, antennas), marking the resources and Capabilities as unassigned and idle.

        :param argin: 'DevLong'
        Sub-Array ID

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.Release

    def is_Release_allowed(self):
        # PROTECTED REGION ID(LfaaMaster.is_Release_allowed) ENABLED START #
        return self.get_state() not in [DevState.OFF,DevState.FAULT,DevState.INIT,DevState.ALARM,DevState.UNKNOWN,DevState.STANDBY,DevState.DISABLE]
        # PROTECTED REGION END #    //  LfaaMaster.is_Release_allowed

    @command(
    )
    @DebugIt()
    def Maintenance(self):
        # PROTECTED REGION ID(LfaaMaster.Maintenance) ENABLED START #
        """
        Transition the LFAA to a MAINTENANCE state.

        :return:None
        """
        pass
        # PROTECTED REGION END #    //  LfaaMaster.Maintenance

# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the LfaaMaster module."""
    # PROTECTED REGION ID(LfaaMaster.main) ENABLED START #
    return run((LfaaMaster,), args=args, **kwargs)
    # PROTECTED REGION END #    //  LfaaMaster.main


if __name__ == '__main__':
    main()
