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

:todo: Implement healthState, taking account of health of this device and
       of the capability invoked on this device
:todo: All commands return a dummy string
"""
__all__ = ["MccsSubarray", "main"]

# PyTango imports
from tango import DebugIt
from tango.server import attribute, command
from tango import DevState

# Additional import
from ska.base import SKASubarray

from . import release


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray prototype.

    :todo: Implement healthState, taking account of health of this device and
           of the capability invoked on this device
    :todo: All commands return a dummy string

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    scanId = attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        doc="The ID of the current scan, set via commands startScan() and "
        "endScan(). A scanId of 0 means that the subarray is idle.",
    )

    stationFQDNs = attribute(
        dtype=("DevString",),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the Stations "
        "allocated to this Subarray",
    )

    tileFQDNs = attribute(
        dtype=("DevString",),
        max_dim_x=8192,
        format="%s",
        polling_period=1000,
        doc="Array holding the full qualified device names of the Tiles "
        "allocated to this Subarray",
    )

    stationBeamFQDNs = attribute(
        dtype=("DevString",),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the Station "
        "Beams allocated to this Subarray",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsSubarray."""
        SKASubarray.init_device(self)

        self.set_state(DevState.INIT)

        self._scan_id = -1
        self._station_FQDNs = []
        self.set_change_event("stationFQDNs", True, True)
        self.set_archive_event("stationFQDNs", True, True)
        self._tile_FQDNs = []
        self._station_beam_FQDNs = []

        self._build_state = release.get_release_info()
        self._version_id = release.version

        # Any other initialisation code goes here,
        # after setting state to INIT,
        # but before setting state to OFF

        self.set_state(DevState.OFF)  # subarray is empty

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

    def read_scanId(self):

        """Return the scanId attribute."""
        return self._scan_id

    def read_stationFQDNs(self):

        """Return the stationFQDNs attribute."""
        return self._station_FQDNs

    def read_tileFQDNs(self):

        """Return the tileFQDNs attribute."""
        return self._tile_FQDNs

    def read_stationBeamFQDNs(self):

        """Return the stationBeamFQDNs attribute."""
        return self._station_beam_FQDNs

    # --------
    # Commands
    # --------

    @command(
        dtype_in="DevString",
        doc_in="a JSON specification of the subarray scan configuration",
        dtype_out="DevString",
        doc_out="ASCII string that indicates status, for information purposes "
        "only",  # noqa: E501
    )
    @DebugIt()
    def configureScan(self, argin):

        """Configure the subarray

        :todo: This method is a stub that does nothing but return a dummy
               string.
        :param argin: a JSON specification of the subarray scan configuration
        :type argin: DevString
        :return: ASCII String that indicates status, for information purposes
                 only
        :rtype: DevString
        """
        return (
            "Dummy ASCII string returned from "
            "MccsSubarray.configureScan() to indicate status, for "
            "information purposes only"
        )

    @command(
        dtype_in="DevVarLongArray",
        doc_in="Specification of the segment of the transient buffer to send,"
        "comprising:"
        "1. Start time (timestamp: milliseconds since UNIX epoch)"
        "2. End time (timestamp: milliseconds since UNIX epoch)"
        "3. Dispersion measure"
        "Together, these parameters narrow the selection of transient"
        "buffer data to the period of time and frequencies that are of"
        "interest."
        ""
        "Additional metadata, such as the ID of a triggering Scheduling"
        "Block, may need to be supplied to allow SDP to assign data"
        "ownership correctly (TBD75).",
        dtype_out="DevString",
        doc_out="ASCII string that indicates status, for information purposes" "only",
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):

        """Cause the subarray to send the requested segment of the transient
        buffer to SDP. The requested segment is specified by:

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
        return (
            "Dummy ASCII string returned from "
            "MccsSubarray.sendTransientBuffer() to indicate status, for "
            "information purposes only"
        )


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """Main function of the MccsSubarray module."""

    """mainline for module"""
    return MccsSubarray.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
