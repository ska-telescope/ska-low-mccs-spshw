# -*- coding: utf-8 -*-
#
# This file is part of the SKA Software lfaa-lmc-prototype project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MCCS Subarray

MccsSubarray is the Tango device class for the MCCS Subarray prototype.

:todo: All MccsSubarray commands are functionless stubs
"""
__all__ = ["MccsSubarray", "main"]

# PyTango imports
from tango import DebugIt
from tango import AttrWriteType
from tango.server import attribute, command
from tango import DevState
from tango import Except, ErrSeverity

# Additional import
from ska.base import SKASubarray
from ska.base.control_model import AdminMode, ObsState
import ska.mccs.release as release


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray prototype.

    :todo: All commands are functionless stubs
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
        Initialises the attributes and properties of the MccsSubarray.
        """
        self.set_state(DevState.INIT)
        SKASubarray.init_device(self)
        # push back to DevState.INIT again because we are still
        # initialising, and SKASubarray.init_device() prematurely pushes to
        #  DevState.DISABLE
        self.set_state(DevState.INIT)

        # The default adminMode is MAINTENANCE. But fear not: adminMode is a
        # memorized attribute, and shortly after init_device() has completed,
        # the Tango subsystem will write the memorized value. So this
        # assignment will only 'stick' when there is no memorized value.
        self._admin_mode = AdminMode.MAINTENANCE

        self._scan_id = -1
        self._station_FQDNs = []
        self.set_change_event("stationFQDNs", True, True)
        self.set_archive_event("stationFQDNs", True, True)
        self._tile_FQDNs = []
        self._station_beam_FQDNs = []

        self._build_state = release.get_release_info()
        self._version_id = release.version

        # Any other initialisation code goes here.

        # The subarray may take some time to initialize, so we should assume that
        # this command will set the obsState to the transient INIT state,
        # instantiate some asnychronous code to effect/monitor the initialisation
        # process, and return. It is up to that asynchronous code to update the
        # state to DISABLE / OFF upon completion. Therefore, we don't set the
        # state here. Instead, we handle that in a separate `_init_completed`
        # method. This can be called directly if initialisation is implemented
        # entirely synchronously. If configuring is handled asynchronously, the
        # method should be provided to the thread as a completion callback.
        self._init_completed()

    def _init_completed(self):
        """
        Callback function for completion of initialisation. Responsible for
        setting the post-init device stateα
        """
        self._require("_init_completed", None, [DevState.INIT], None)
        if self._admin_mode in [AdminMode.OFFLINE, AdminMode.NOT_FITTED]:
            self.set_state(DevState.DISABLE)
        else:
            self.set_state(DevState.OFF)

        self.logger.info("MCCS Subarray device initialised.")

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ------------------
    # Attribute methods
    # ------------------
    def read_scanId(self):
        """
        Return the scanId attribute.
        """
        return self._scan_id

    def read_stationFQDNs(self):
        """
        Return the stationFQDNs attribute.
        """
        return self._station_FQDNs

    def read_tileFQDNs(self):
        """
        Return the tileFQDNs attribute.
        """
        return self._tile_FQDNs

    def read_stationBeamFQDNs(self):
        """
        Return the stationBeamFQDNs attribute.
        """
        return self._station_beam_FQDNs

    # -------------------------------------
    # Base class attribute method overrides
    # -------------------------------------
    def write_adminMode(self, value):
        """
        Write the new adminMode value. Used by TM to put the subarray online
        and to take it offline. This action may trigger additional actions and
        state changes as follows:

        +-----------+-------+-------+--------+------------+--------------------+
        |         To|ONLINE |MAINT- |OFFLINE              |NOT_FITTED          |
        |           |       |ENANCE |                     |                    |
        |From       |       |       |                     |                    |
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

        #. The subarray can change between ONLINE and MAINTENANCE at any time,
           with no further change to the state machine.

        #. The subarray can be taken OFFLINE or put into NOT_FITTED mode at any
           time, in which case it aborts whatever it was doing, deconfigures,
           releases its resources, and changes State to DISABLED.

        #. When the subarray is placed into ONLINE or MAINTENANCE mode from
           OFFLINE or NOT_FITTED mode, the subarray is being put online, so the
           state changes from DISABLE to OFF.

        :param value: the new admin mode
        :type value: AdminMode enum value
        """
        state = self.get_state()
        if value != self._admin_mode:  # we're changing mode
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

    # ---------------------------------------
    # Base class command gatekeeper overrides
    # ---------------------------------------
    def _require(self, command, admin_modes, dev_states, obs_states, throw=True):
        """
        Helper method that checks whether the device is currently in one of a
        defined set of states, and throws a tango.DevFailed exception if it is
        not. This method exists because if is_[Commandi]_allowed() simply
        returns False, the tango subsystem will throw a DevFailed exception
        containing an inappropriate error message that blames the refusal to
        allow the command on device state only. For example, the device might
        disallow command Scan() because obsState==IDLE, and the DevFailed
        exception will wrongly complain that State==ON. We avoid this problem
        by beating tango to the punch and throwing the exception ourselves.

        :param command: the name of the command we are testing state for
        :type command: string
        :param states: the allowable states for this command
        :type states: list of DevState
        :param admin_modes: the allowable admin modes for this command
        :type adminModes: list of AdminMode
        :param obsStates: the allowable obs states for this command
        :type obsStates: list of ObsState
        :param throw: whether to throw a DevFailed exception if the required
        state is not met
        :type throw: boolean (default True)
        :raises DevFailed: if argument `throw` is True, then if the state is not
        amongst the defined states, then a DevFailed exception is thrown.
        :return True iff the current state, admin mode and observation state are
        in, respectively, the provided lists of states, admin modes and
        obs states. False otherwise, but if argument `throw` is True, then the
        returning of False will never occur.
        :rtype: boolean
        """

        def throw_exception(attribute, value):
            Except.throw_exception(
                "API_CommandFailed",
                "Command {} is not allowed in device {} {}.".format(command,
                                                                    attribute,
                                                                    value),
                "is_{}_allowed".format(command),
                ErrSeverity.ERR
            )

        checks = [
            ("state", self.get_state(), dev_states),
            ("adminMode", self._admin_mode, admin_modes),
            ("obsState", self._obs_state, obs_states)
        ]

        for (name, value, required) in checks:
            if required is None:
                continue
            if value not in required:
                if throw:
                    throw_exception(name, value)
                else:
                    return False
        return True

    # ----------------------------
    # Base class command overrides
    # ----------------------------

    def is_ConfigureCapability_allowed(self):
        """
        Check whether command ConfigureCapability is permitted in this device state.

        Overriding because base class requires device to be in adminMode ONLINE,
        whereas it should also be possible to configure capabilities while in
        adminMode=MAINTENANCE.
        """
        return self._require("ConfigureCapability",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.IDLE, ObsState.READY])

    @command(
        dtype_in='DevVarLongStringArray',
        doc_in="[Number of instances to add][Capability types]",
    )
    @DebugIt()
    def ConfigureCapability(self, argin):
        """
        Configure one or more capability instances

        Overriding to support asynchronous callback
        """
        super().ConfigureCapability(argin)

        # push back to CONFIGURING because the base class pushes to READY
        self._obs_state = ObsState.CONFIGURING

        # Any other configuration code goes here.

        # The subarray may take some time to configure, so we should assume that
        # this command will set the obsState to the transient CONFIGURING state,
        # instantiate some asynchronous code to effect/monitor the configuring
        # process, and return. It is up to that asynchronous code to update the
        # obsState to READY upon completion. Therefore, we don't set the
        # obsState to READY here. Instead, we handle that in a separate
        # `_configure_completed` method. This can be called directly if
        # configuring is implemented entirely synchronously. If configuring is
        # handled asynchronously, the method should be provided to the thread as
        # a completion callback.
        self._configure_completed()

    def _configure_completed(self):
        """
        Callback function for completion of configuration. Responsible for
        setting the post-init device state
        """
        self._require("_configure_completed",
                      [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                      [DevState.ON],
                      [ObsState.CONFIGURING])
        self._obs_state = ObsState.READY

    def is_DeconfigureCapability_allowed(self):
        """
        Check whether command DeconfigureCapability() is permitted in this
        device state.

        Overriding because base class requires device to be in:
        * obsState IDLE, but in this state it has no configured capabilities to
        deconfigure.
        * adminMode ONLINE only, whereas it should also be possible in adminMode
        MAINTENANCE.
        """
        return self._require("DeconfigureCapability",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.READY])

    @command(
        dtype_in='DevVarLongStringArray',
        doc_in="[Number of instances to remove][Capability types]",
    )
    @DebugIt()
    def DeconfigureCapability(self, argin):
        """
        Deconfigure one or more instances of one or more capabilities.

        Overriding to ensure device ends up in the right state.

        :todo: The control model assumes that configuring may take some time,
            and allows for a transient CONFIGURING state. We implement it as if
            it will eventually require asynchronous implementation. But what
            about deconfiguring? Here we assume it is fast and will not require
            an asynchronous implementation, nor use of the transient CONFIGURING
            state.
        """
        super().DeconfigureCapability(argin)
        if not any(self._configured_capabilities.values()):
            self._obs_state = ObsState.IDLE

    def is_DeconfigureAllCapabilities_allowed(self):
        """
        Check whether command DeconfigureAllCapabilities() is permitted in this
        device state.

        Overriding because base class requires device to be in:
        * obsState IDLE, but in this state it has no configured capabilities to
        deconfigure.
        * adminMode ONLINE, whereas it should also be possible in adminMode
        MAINTENANCE.
        """
        return self._require("DeconfigureCapability",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.READY])

    @command(dtype_in='str', doc_in="Capability type",)
    @DebugIt()
    def DeconfigureAllCapabilities(self, argin):
        """
        Deconfigure all instances of a given capability type.

        Overriding to ensure device ends up in the right state.

        :todo: The control model assumes that configuring may take some time,
            and allows for a transient CONFIGURING state. We implement it as if
            it will eventually require asynchronous implementation. But what
            about deconfiguring? Here we assume it is fast and will not require
            an asynchronous implementation, nor use of the transient CONFIGURING
            state.
        """
        super().DeconfigureAllCapabilities(argin)
        if not any(self._configured_capabilities.values()):
            self._obs_state = ObsState.IDLE

    def is_ReleaseResources_allowed(self):
        """
        Check whether command ReleaseResources() is permitted in this device state.

        Overriding because base class allows releasing of resources when the
        subarray is in OFF state (i.e. it is already empty).
        """
        return self._require("ReleaseResources",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.IDLE])

    @command(
        dtype_in=('str',),
        doc_in="List of resources to remove from the subarray.",
        dtype_out=('str',),
        doc_out="List of resources removed from the subarray.",
    )
    @DebugIt()
    def ReleaseResources(self, argin):
        """
        Release some resources.

        Overriding in order to set state back to OFF if array has been emptied.
        """
        released_resources = super().ReleaseResources(argin)
        if not self._assigned_resources:
            self.set_state(DevState.OFF)
        return released_resources

    def is_ReleaseAllResources_allowed(self):
        """
        Overriding because base class allows releasing of resources when the
        subarray is in OFF state (i.e. it is already empty).
        """
        return self._require("ReleaseAllResources",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.IDLE])

    @command(
        dtype_out=('str',),
        doc_out="List of resources removed from the subarray.",
    )
    @DebugIt()
    def ReleaseAllResources(self):
        """
        Release all resources.

        Overriding in order to set state back to OFF
        """
        released_resources = super().ReleaseAllResources()
        self.set_state(DevState.OFF)
        return released_resources

    def is_Scan_allowed(self):
        """
        Check device state to confirm that command `Scan()` is allowed.
        """
        return self._require("Scan",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.READY])

    @command(
        dtype_in=('str',),
    )
    @DebugIt()
    def Scan(self, argin):
        """
        Start scanning.

        Overriding in order to set obsState to SCANNING.
        """
        super().Scan(argin)
        self._obs_state = ObsState.SCANNING

    def _scan_completed(self):
        """
        Callback function for completion of scan. Responsible for
        setting the post-init device state
        """
        self._require("_configure_completed",
                      [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                      [DevState.ON],
                      [ObsState.SCANNING, ObsState.PAUSED])
        self._obs_state = ObsState.READY

    def is_EndScan_allowed(self):
        """
        Check device state to confirm that command `EndScan()` is allowed.
        """
        return self._require("EndScan",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.SCANNING, ObsState.PAUSED])

    @command()
    @DebugIt()
    def EndScan(self):
        """
        Ends the scan.

        Overriding in order to set obsState to READY.
        """
        super().EndScan()
        self._obs_state = ObsState.READY

    def is_EndSB_allowed(self):
        """
        Check device state to confirm that command `EndSB()` is allowed.
        """
        return self._require("EndSB",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.READY])

    @command()
    @DebugIt()
    def EndSB(self):
        """
        Signals the end of the scanblock.

        Overriding in order to change obsState to IDLE
        """
        super().EndSB()
        self._obs_state = ObsState.IDLE

    def is_Abort_allowed(self):
        """
        Check device state to confirm that command `Abort()` is allowed.
        """
        return self._require("Abort",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.CONFIGURING, ObsState.READY,
                              ObsState.SCANNING, ObsState.PAUSED])

    @command()
    @DebugIt()
    def Abort(self):
        """
        Abort the scan.

        Overriding in order to set obsState to ABORTED.
        """
        super().Abort()
        self._obs_state = ObsState.ABORTED

    def is_Reset_allowed(self):
        """
        Check whether Reset() is allowed in this device state

        Overriding because base class allows reset at any time, whereas this
        command seems to be defined for subarrays as 'stop what you're doing and
        deconfigure but don't release your resources.' This semantics only makes
        sense when we are in ON state with an obsState not IDLE.
        """
        return self._require("Reset",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.CONFIGURING, ObsState.READY,
                              ObsState.SCANNING, ObsState.PAUSED,
                              ObsState.ABORTED])

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

    def is_Pause_allowed(self):
        """
        Check device state to confirm that command `Pause()` is allowed.
        """
        return self._require("Pause",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.SCANNING])

    @command()
    @DebugIt()
    def Pause(self):
        """
        Pause the scan

        Overriding in order to set obsState to PAUSED
        """
        super().Pause()
        self._obs_state = ObsState.PAUSED

    def is_Resume_allowed(self):
        """
        Check device state to confirm that command `Resume()` is allowed.
        """
        return self._require("Resume",
                             [AdminMode.ONLINE, AdminMode.MAINTENANCE],
                             [DevState.ON],
                             [ObsState.PAUSED])

    @command()
    @DebugIt()
    def Resume(self):
        """
        Pause the scan

        Overriding in order to set obsState to PAUSED
        """
        super().Resume()
        self._obs_state = ObsState.SCANNING

    # ---------------------
    # MccsSubarray Commands
    # ---------------------

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
        doc_out="ASCII string that indicates status, for information purposes only",
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):
        """
        Cause the subarray to send the requested segment of the transient buffer
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
        return (
            "Dummy ASCII string returned from "
            "MccsSubarray.sendTransientBuffer() to indicate status, for "
            "information purposes only"
        )


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Mainline for the MccsSubarray module.
    """
    return MccsSubarray.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
