# -*- coding: utf-8 -*-
#
# This file is part of the MccsSubarray project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MCCS Subarray

MccsSubarray is the Tango device class for the MCCS Subarray prototype.

:todo: This device has device property `skaLevel` with default value 2, as
       required. It also inherits device property `SkaLevel` with default
       value 4, which is not correct for this device. The `skaLevel`/
       `SkaLevel` conflict needs to be resolved.
:todo: Implement healthState, taking account of health of this device and
       of the capability invoked on this device
:todo: All commands return a dummy string
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
#from SKASubarray import SKASubarray
# Additional import
# PROTECTED REGION ID(MccsSubarray.additionnal_import) ENABLED START #
#REMEMBER TO COMMENT OUT "from SKASubarray import SKASubarray" above
from ska.base import SKASubarray
from ska.base.control_model import (HealthState, AdminMode, ObsState,
                                    ObsMode, ControlMode, SimulationMode,
                                    TestMode, LoggingLevel)
# PROTECTED REGION END #    //  MccsSubarray.additionnal_import

__all__ = ["MccsSubarray", "main"]


#class AdminMode(enum.IntEnum):
#    """Python enumerated type for AdminMode attribute."""
#
#
#class ControlMode(enum.IntEnum):
#    """Python enumerated type for ControlMode attribute."""
#
#
#class HealthState(enum.IntEnum):
#    """Python enumerated type for HealthState attribute."""
#
#
#class LoggingLevel(enum.IntEnum):
#    """Python enumerated type for LoggingLevel attribute."""
#
#
#class ObsMode(enum.IntEnum):
#    """Python enumerated type for ObsMode attribute."""
#
#
#class ObsState(enum.IntEnum):
#    """Python enumerated type for ObsState attribute."""
#
#
#class SimulationMode(enum.IntEnum):
#    """Python enumerated type for SimulationMode attribute."""
#
#
#class TestMode(enum.IntEnum):
#    """Python enumerated type for TestMode attribute."""
#

class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray prototype.

    :todo: This device has device property `skaLevel` with default value 2, as
           required. It also inherits device property `SkaLevel` with default
           value 4, which is not correct for this device. The `skaLevel`/
           `SkaLevel` conflict needs to be resolved.
    :todo: Implement healthState, taking account of health of this device and
           of the capability invoked on this device
    :todo: All commands return a dummy string

    **Properties:**

    - Device Property
        skaLevel
            - Indication of importance of the device in the SKA hierarchy
              to support drill-down navigation
            - Type:'DevShort'
    """
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(MccsSubarray.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsSubarray.class_variable

    # -----------------
    # Device Properties
    # -----------------







    skaLevel = device_property(
        dtype='DevShort', default_value=2
    )

    # ----------
    # Attributes
    # ----------














    scanID = attribute(
        dtype='DevLong',
        format="%i",
        polling_period=1000,
        doc="The ID of the current scan, set via commands startScan() and endScan(). A scanID of 0 means that the subarray is idle.",
    )




    stationFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the Stations allocated to this Subarray",
    )

    tileFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=8192,
        format="%s",
        polling_period=1000,
        doc="Array holding the full qualified device names of the Tiles allocated to this Subarray",
    )

    stationBeamFQDNs = attribute(
        dtype=('DevString',),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the Station Beams allocated to this Subarray",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsSubarray."""
        SKASubarray.init_device(self)
        self.set_change_event("stationFQDNs", True, True)
        self.set_archive_event("stationFQDNs", True, True)
        # PROTECTED REGION ID(MccsSubarray.init_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsSubarray.init_device

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsSubarray.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsSubarray.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsSubarray.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsSubarray.delete_device
    # ------------------
    # Attributes methods
    # ------------------

    def read_scanID(self):
        # PROTECTED REGION ID(MccsSubarray.scanID_read) ENABLED START #
        """Return the scanID attribute."""
        return 0
        # PROTECTED REGION END #    //  MccsSubarray.scanID_read

    def read_stationFQDNs(self):
        # PROTECTED REGION ID(MccsSubarray.stationFQDNs_read) ENABLED START #
        """Return the stationFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  MccsSubarray.stationFQDNs_read

    def read_tileFQDNs(self):
        # PROTECTED REGION ID(MccsSubarray.tileFQDNs_read) ENABLED START #
        """Return the tileFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  MccsSubarray.tileFQDNs_read

    def read_stationBeamFQDNs(self):
        # PROTECTED REGION ID(MccsSubarray.stationBeamFQDNs_read) ENABLED START #
        """Return the stationBeamFQDNs attribute."""
        return ('',)
        # PROTECTED REGION END #    //  MccsSubarray.stationBeamFQDNs_read

    # --------
    # Commands
    # --------

    @command(
        dtype_in='DevString',
        doc_in="a JSON specification of the subarray scan configuration",
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def configureScan(self, argin):
        # PROTECTED REGION ID(MccsSubarray.configureScan) ENABLED START #
        """Configure the subarray

        :todo: This method is a stub that does nothing but return a dummy
               string.
        :param argin: a JSON specification of the subarray scan configuration
        :type argin: DevString
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        return ("Dummy ASCII string returned from "
                "MccsSubarray.configureScan() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.configureScan

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def startScan(self):
        # PROTECTED REGION ID(MccsSubarray.startScan) ENABLED START #
        """Cause the subarray to start sending station beam data to CSP

        :todo: This method is a stub that calls the inherited Scan method,
               and returns a dummy string. The `startScan`/`Scan` conflict
               needs to be fixed so that this function overloads rather than
               calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Scan()
        return ("Dummy ASCII string returned from MccsSubarray.startScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.startScan

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def endScan(self):
        # PROTECTED REGION ID(MccsSubarray.endScan) ENABLED START #
        """Cause the subarray to stop transmission of output products.
        Pointing and calibration jobs are left configured so that
        subsequent scans requiring the same parameters do not need to be
        reconfigured.
        Otherwise, the subarray configuration remains the same, and the command
        startScan() can be used to return to scanning.

        :todo: This method is a stub that calls the inherited EndScan method,
               and returns a dummy string. The `endScani`/`EndScan` conflict
               needs to be fixed so that this function overloads rather than
               calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.EndScan()
        return ("Dummy ASCII string returned from MccsSubarray.endScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.endScan

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def releaseResources(self):
        # PROTECTED REGION ID(MccsSubarray.releaseResources) ENABLED START #
        """Cause the subarray to release all Stations, Tiles and Station Beams,
        and transition to idle. The released Stations, Tiles and Station Beams
        are returned to the pool of the unassigned resources.

        :todo: This method is a stub that does nothing but return a dummy
               string.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        return ("Dummy ASCII string returned from "
                "MccsSubarray.releaseResources() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.releaseResources

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def pauseScan(self):
        # PROTECTED REGION ID(MccsSubarray.pauseScan) ENABLED START #
        """Cause the sub-array to stop transmitting output products (other
        sub-arrays may continue normal operation). While a scan is paused, the
        subarray does not raise alarms if updates for sky coordinates and
        required calibration parameters are not received.

        :todo: This method is a stub that calls the inherited Pause method, and
               returns a dummy string. The `pauseScan`/`Pause` conflict needs
               to be fixed so that this function overloads rather than calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Pause()
        return ("Dummy ASCII string returned from MccsSubarray.pauseScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.pauseScan

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def resumeScan(self):
        # PROTECTED REGION ID(MccsSubarray.resumeScan) ENABLED START #
        """Cause the subarray to resume scanning after having been paused

        :todo: This method is a stub that calls the inherited Resume method,
               and returns a dummy string. The `resume`/`Resume` conflict needs
               to be fixed so that this function overloads rather than calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Resume()
        return ("Dummy ASCII string returned from MccsSubarray.resumeScan() "
                "to indicate status, for information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.resumeScan

    @command(
        dtype_in='DevVarLongArray',
        doc_in="Specification of the segment of the transient buffer to send, comprising:"
               "1. Start time (timestamp: milliseconds since UNIX epoch)"
               "2. End time (timestamp: milliseconds since UNIX epoch)"
               "3. Dispersion measure"
               "Together, these parameters narrow the selection of transient buffer data to the period of time and frequencies that are of interest."
               ""
               "Additional metadata, such as the ID of a triggering Scheduling Block, may need to be supplied to allow SDP to assign data ownership correctly (TBD75).",
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):
        # PROTECTED REGION ID(MccsSubarray.sendTransientBuffer) ENABLED START #
        """Cause the subarray to send the requested segment of the transient buffer
        to SDP. The requested segment is specified by:

        1. Start time (timestamp: milliseconds since UNIX epoch)
        2. End time (timestamp: milliseconds since UNIX epoch)
        3. Dispersion measure

        Together, these parameters narrow the selection of transient buffer
        data to the period of time and frequencies that are of interest.

        Additional metadata, such as the ID of a triggering Scheduling Block,
        may need to be supplied to allow SDP to assign data ownership correctly
        (TBD75).

        :todo: This method is a stub that does nothing but return a dummy
               string.
        :param argin: Specification of the segment of the transient buffer to
                      send
        :type argin: DevVarLongArray
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        return ("Dummy ASCII string returned from "
                "MccsSubarray.sendTransientBuffer() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.sendTransientBuffer

    @command(
        dtype_out='DevString',
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def abort(self):
        # PROTECTED REGION ID(MccsSubarray.abort) ENABLED START #
        """Cause the array to abort the current observation on this subarray. Output
        to CSP is stopped, pointing/calibration activities are terminated, and
        Tiles are deconfigured.

        :todo: This method is a stub that calls the inherited Abort method, and
               returns a dummy string. The `abort`/`Abort` conflict needs to be
               fixed so that this function overloads rather than calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Abort()
        return ("Dummy ASCII string returned from MccsSubarray.abort() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  MccsSubarray.abort

# ----------
# Run server
# ----------

def main(args=None, **kwargs):
    """Main function of the MccsSubarray module."""
    # PROTECTED REGION ID(MccsSubarray.main) ENABLED START #
    """mainline for module"""
    return run((MccsSubarray,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsSubarray.main


if __name__ == '__main__':
    main()

