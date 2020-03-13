# -*- coding: utf-8 -*-
#
# This file is part of the LfaaSubarray project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" Lfaa Subarray

LfaaSubarray is the Tango device class for the Lfaa Subarray prototype.

:todo: This device has device property `skaLevel` with default value 2, as
       required. It also inherits device property `SkaLevel` with default
       value 4, which is not correct for this device. The `skaLevel`/
       `SkaLevel` conflict needs to be resolved.
:todo: Implement healthState, taking account of health of this device and
       of the capability invoked on this device
:todo: All commands return a dummy string
"""

# PyTango imports
import PyTango
from PyTango import DebugIt
from PyTango.server import run
from PyTango.server import Device, DeviceMeta
from PyTango.server import attribute, command
from PyTango.server import device_property
from PyTango import AttrQuality, DispLevel, DevState
from PyTango import AttrWriteType, PipeWriteType
#from SKASubarray import SKASubarray
# Additional import
# PROTECTED REGION ID(LfaaSubarray.additionnal_import) ENABLED START #
### REMEMBER TO COMMENT OUT "from SKASubarray import SKASubarray" ABOVE
from skabase.SKASubarray import SKASubarray
# PROTECTED REGION END #    //  LfaaSubarray.additionnal_import

__all__ = ["LfaaSubarray", "main"]


class LfaaSubarray(SKASubarray):
    """
    LfaaSubarray is the Tango device class for the Lfaa Subarray prototype.
    
    :todo: This device has device property `skaLevel` with default value 2, as
           required. It also inherits device property `SkaLevel` with default
           value 4, which is not correct for this device. The `skaLevel`/
           `SkaLevel` conflict needs to be resolved.
    :todo: Implement healthState, taking account of health of this device and
           of the capability invoked on this device
    :todo: All commands return a dummy string
    """
    __metaclass__ = DeviceMeta
    # PROTECTED REGION ID(LfaaSubarray.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  LfaaSubarray.class_variable

    # -----------------
    # Device Properties
    # -----------------







    skaLevel = device_property(
        dtype='int16', default_value=2
    )

    # ----------
    # Attributes
    # ----------














    scanID = attribute(
        dtype='int',
        format="%i",
        doc="The ID of the current scan, set via commands startScan() and endScan(). A scanID of 0 means that the subarray is idle.",
    )




    stationFQDNs = attribute(
        dtype=('str',),
        max_dim_x=512,
        format="%s",
        doc="Array holding the fully qualified device names of the Stations allocated to this Subarray",
    )

    tileFQDNs = attribute(
        dtype=('str',),
        max_dim_x=8192,
        format="%s",
        doc="Array holding the full qualified device names of the Tiles allocated to this Subarray",
    )

    stationBeamFQDNs = attribute(
        dtype=('str',),
        max_dim_x=512,
        format="%s",
        doc="Array holding the fully qualified device names of the Station Beams allocated to this Subarray",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        SKASubarray.init_device(self)
        self.set_change_event("stationFQDNs", True, True)
        self.set_archive_event("stationFQDNs", True, True)
        # PROTECTED REGION ID(LfaaSubarray.init_device) ENABLED START #
        """Initialise the attributes and properties of the LfaaSubarray."""
        # PROTECTED REGION END #    //  LfaaSubarray.init_device

    def always_executed_hook(self):
        # PROTECTED REGION ID(LfaaSubarray.always_executed_hook) ENABLED START #
        """Method always executed before any TANGO command is executed."""
        #pass
        # PROTECTED REGION END #    //  LfaaSubarray.always_executed_hook

    def delete_device(self):
        # PROTECTED REGION ID(LfaaSubarray.delete_device) ENABLED START #
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released. This method is called by the device
        destructor and by the device Init command.
        """
        #pass
        # PROTECTED REGION END #    //  LfaaSubarray.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_scanID(self):
        # PROTECTED REGION ID(LfaaSubarray.scanID_read) ENABLED START #
        """Return the scanID attribute."""
        return 0
        # PROTECTED REGION END #    //  LfaaSubarray.scanID_read

    def read_stationFQDNs(self):
        # PROTECTED REGION ID(LfaaSubarray.stationFQDNs_read) ENABLED START #
        """Return the stationFQDNs attribute."""
        return ['']
        # PROTECTED REGION END #    //  LfaaSubarray.stationFQDNs_read

    def read_tileFQDNs(self):
        # PROTECTED REGION ID(LfaaSubarray.tileFQDNs_read) ENABLED START #
        """Return the tileFQDNs attribute."""
        return ['']
        # PROTECTED REGION END #    //  LfaaSubarray.tileFQDNs_read

    def read_stationBeamFQDNs(self):
        # PROTECTED REGION ID(LfaaSubarray.stationBeamFQDNs_read) ENABLED START #
        """Return the stationBeamFQDNs attribute."""
        return ['']
        # PROTECTED REGION END #    //  LfaaSubarray.stationBeamFQDNs_read


    # --------
    # Commands
    # --------

    @command(
    dtype_in='str', 
    doc_in="a JSON specification of the subarray scan configuration", 
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def configureScan(self, argin):
        # PROTECTED REGION ID(LfaaSubarray.configureScan) ENABLED START #
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
                "LfaaSubarray.configureScan() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.configureScan

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def startScan(self):
        # PROTECTED REGION ID(LfaaSubarray.startScan) ENABLED START #
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
        return ("Dummy ASCII string returned from LfaaSubarray.startScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.startScan

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def endScan(self):
        # PROTECTED REGION ID(LfaaSubarray.endScan) ENABLED START #
        """Cause the subarray to stop transmission of output products.
        LFAA pointing and calibration jobs are left configured so that
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
        return ("Dummy ASCII string returned from LfaaSubarray.endScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.endScan

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def releaseResources(self):
        # PROTECTED REGION ID(LfaaSubarray.releaseResources) ENABLED START #
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
                "LfaaSubarray.releaseResources() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.releaseResources

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def pauseScan(self):
        # PROTECTED REGION ID(LfaaSubarray.pauseScan) ENABLED START #
        """Cause the sub-array to stop transmitting output products (other
        sub-arrays may continue normal operation). While a scan is paused, the
        LFAA subarray does not raise alarms if updates for sky coordinates and
        required calibration parameters are not received.

        :todo: This method is a stub that calls the inherited Pause method, and
               returns a dummy string. The `pauseScan`/`Pause` conflict needs
               to be fixed so that this function overloads rather than calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Pause()
        return ("Dummy ASCII string returned from LfaaSubarray.pauseScan() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.pauseScan

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def resumeScan(self):
        # PROTECTED REGION ID(LfaaSubarray.resumeScan) ENABLED START #
        """Cause the subarray to resume scanning after having been paused

        :todo: This method is a stub that calls the inherited Resume method,
               and returns a dummy string. The `resume`/`Resume` conflict needs
               to be fixed so that this function overloads rather than calling.
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        self.Resume()
        return ("Dummy ASCII string returned from LfaaSubarray.resumeScan() "
                "to indicate status, for information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.resumeScan

    @command(
    dtype_in=('int',), 
    doc_in="Specification of the segment of the transient buffer to send, comprising:\n1. Start time (timestamp: milliseconds since UNIX epoch)\n2. End time (timestamp: milliseconds since UNIX epoch)\n3. Dispersion measure\nTogether, these parameters narrow the selection of transient buffer data to the period of time and frequencies that are of interest.\n\nAdditional metadata, such as the ID of a triggering Scheduling Block, may need to be supplied to allow SDP to assign data ownership correctly (TBD75).", 
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):
        # PROTECTED REGION ID(LfaaSubarray.sendTransientBuffer) ENABLED START #
        """Cause the LFAA to send the requested segment of the transient buffer
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
                "LfaaSubarray.sendTransientBuffer() to indicate status, for "
                "information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.sendTransientBuffer

    @command(
    dtype_out='str', 
    doc_out="ASCII string that indicates status, for information purposes only", 
    )
    @DebugIt()
    def abort(self):
        # PROTECTED REGION ID(LfaaSubarray.abort) ENABLED START #
        """Cause LFAA to abort the current observation on this subarray. Output
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
        return ("Dummy ASCII string returned from LfaaSubarray.abort() to "
                "indicate status, for information purposes only")
        # PROTECTED REGION END #    //  LfaaSubarray.abort

# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    # PROTECTED REGION ID(LfaaSubarray.main) ENABLED START #
    """mainline for module"""
    return run((LfaaSubarray,), args=args, **kwargs)
    # PROTECTED REGION END #    //  LfaaSubarray.main

if __name__ == '__main__':
    main()
