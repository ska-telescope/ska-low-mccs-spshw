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

# base imports
from threading import Lock

# PyTango imports
from tango import DebugIt
from tango import AttrWriteType
from tango.server import attribute, command
from tango import DevState

# Additional import
from ska.base import SKASubarray
from ska.base.control_model import AdminMode, ObsState
import ska.mccs.release as release


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray prototype.

    :todo: Some writes/attributes cause multiple state/mode changes. This should
           be atomic. Does we need to use a thread lock to ensure thread safety,
           or does Tango handle this for us?
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
        doc="The ID of the current scan, set via commands Scan() and "
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

    # --------------------
    # Inherited attributes
    # --------------------
    adminMode = attribute(
        dtype=AdminMode,
        access=AttrWriteType.READ_WRITE,
        memorized=True,
        doc="The admin mode reported for this device. It may interpret the current "
            "device condition and condition of all managed devices to set this. "
            "Most possibly an aggregate attribute.",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """
        Initialises the attributes and properties of the MccsSubarray.i
        """
        self._state_lock = Lock()  # to atomically change multiple states/modes

        with self._state_lock:
            self.set_state(DevState.INIT)
            SKASubarray.init_device(self)
            # push back to DevState.INIT again because we are still
            # initialising, and SKASubarray.init_device() prematurely pushes to
            #  DevState.DISABLE
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
            # but before setting state to DISABLE

            # We need to initialise admin mode from the memorized value, but I
            # don't know how to do that, and the base classes are incorrectly
            # initialising it to ONLINE anyhow, so we'll go with that for now.
            if self._admin_mode in [AdminMode.OFFLINE, AdminMode.NOT_FITTED]:
                self.set_state(DevState.DISABLE)
            else:
                self.set_state(DevState.OFF)

        self.logger.info("MCCS Subarray device initialised.")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ------------------
    # Attribute methods
    # ------------------

    def read_scanId(self):

        """Return the scanId attribute."""
        return self._scan_id

    def read_stationFQDNs(self):
        """
        Return the stationFQDNs attribute.
        """
        return self._station_FQDNs

    def read_tileFQDNs(self):

        """Return the tileFQDNs attribute."""
        return self._tile_FQDNs

    def read_stationBeamFQDNs(self):

        """Return the stationBeamFQDNs attribute."""
        return self._station_beam_FQDNs

    # -------------------------------------
    # Base class attribute method overrides
    # -------------------------------------
    def write_adminMode(self, value):
        r"""
        Write the new adminMode value. Used by TM to put the subarray online
        and to take it offline. This action may trigger additional actions and
        state changes as follows:

        +-----------+-------+-------+--------+------------+--------------------+
        |         To|ONLINE |MAINT- |OFFLINE              |NOT_FITTED          |
        |From       |       |ENANCE |                     |                    |
        +-----------+-------+-------+---------------------+--------------------+
        |ONLINE     |N/A    |no     |Reset()              |Reset()             |
        |           |       |further|ReleaseAllResources()|ReleaseAllResource()|
        |           |       |action |[OFF|ON] -> DISABLE  |[OFF|ON] -> DISABLE |
        +-----------+-------+-------+---------------------+--------------------+
        |MAINTENANCE|no     |N/A    |Reset()              |Reset()             |
        |           |further|       |ReleaseAllResources()|ReleaseAllResource()|
        |           |action |       |[OFF|ON] -> DISABLE  |[OFF|ON] -> DISABLE |
        +-----------+-------+-------+---------------------+--------------------+
        |OFFLINE    |DISABLE|DISABLE|N/A                  |no                  |
        |           | -> OFF| -> OFF|                     |further             |
        |           |       |       |                     |action              |
        +-----------+-------+-------+---------------------+--------------------+
        |NOT_FITTED |DISABLE|DISABLE|no further action    |N/A                 |
        |           |->  OFF| -> OFF|                     |                    |
        +-----------+-------+-------+---------------------+--------------------+

        Notes:
        1. The subarray can change between ONLINE and MAINTENANCE at any time,
        with no further change to the state machine.
        2. The subarray can be taken OFFLINE or put into NOT_FITTED mode at any
        time, in which case it aborts whatever it was doing, deconfigures,
        releases its resources, and changes State to DISABLED.
        3. When the subarray is placed into ONLINE or MAINTENANCE mode from
        OFFLINE or NOT_FITTED mode, the subarray is being put online, so the
        state changes from DISABLE to OFF.

        :param value: the new admin mode
        :type value: AdminMode enum value
        """
        state = self.get_state()
        if value != self._admin_mode:  # we're changing mode
            with self._state_lock:
                if value in [AdminMode.ONLINE, AdminMode.MAINTENANCE]:
                    if state == DevState.DISABLE:
                        self.set_state(DevState.OFF)
                elif value in [AdminMode.OFFLINE, AdminMode.NOT_FITTED]:
                    if state != DevState.DISABLE:
                        if state == DevState.ON:
                            self.Reset()
                            self.ReleaseAllResources()
                        self.set_state(DevState.DISABLE)
                super().write_adminMode(value)

    # ----------------------------
    # Base class command overrides
    # ----------------------------
    @command(
        dtype_out=('str',),
        doc_out="List of resources removed from the subarray.",
    )
    @DebugIt()
    def ReleaseAllResources(self):
        """
        Remove all resources to tear down to an empty subarray.
        Overriding in order to set state back to OFF
        """
        released_resources = super().ReleaseAllResources()
        self.set_state(DevState.OFF)
        return released_resources

    @command(
        dtype_in=('str',),
    )
    @DebugIt()
    def Scan(self, argin):
        """
        Starts the scan.
        Overriding in order to set obsState to SCANNING.
        """
        super().Scan(argin)
        self._obs_state = ObsState.SCANNING

    @command()
    @DebugIt()
    def EndScan(self):
        """
        Ends the scan.
        Overriding in order to set obsState to READY.
        """
        super().EndScan()
        self._obs_state = ObsState.READY

    @command()
    @DebugIt()
    def EndSB(self):
        """
        Signals the end of the scanblock.
        Change obsState to IDLE
        """
        super().EndSB()
        self._obs_state = ObsState.IDLE

    @command()
    @DebugIt()
    def Abort(self):
        """
        Abort the scan.
        Overriding in order to set obsState to ABORTED.
        """
        super().Abort()
        self._obs_state = ObsState.ABORTED

    @command()
    @DebugIt()
    def Reset(self):
        """
        Reset the scan
        Overriding in order to conform to state machine
        """

        # if DISABLED, we don't want to do anything
        # if OFF, there's nothing to do
        # Maybe calls from DISABLED and OFF state should be rejected rather than
        # ignored?
        if self.get_state() == DevState.ON:
            # abort any configuring or running scan
            # deconfigure
            self._obs_state = ObsState.IDLE

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
        self._obs_state = ObsState.CONFIGURING
        # do stuff
        self._obs_state = ObsState.READY
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
