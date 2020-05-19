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
from tango import DebugIt, Except, ErrSeverity
from tango import AttrWriteType
from tango.server import attribute, command
from tango import DevState
from tango import DeviceProxy

# Additional import
from ska.base import SKASubarray
from ska.base.control_model import AdminMode, ObsState
import ska.mccs.release as release
from ska.mccs.control_model import ReturnCode
from ska.mccs.control_model import device_check
from ska.mccs.utils import json_input


class MccsSubarray(SKASubarray):
    """
    MccsSubarray is the Tango device class for the MCCS Subarray
    prototype.

    :todo: All commands are functionless stubs
    """

    device_check.register("states", lambda device, states: device.get_state() in states)
    device_check.register(
        "admin_modes", lambda device, adminModes: device._admin_mode in adminModes
    )
    device_check.register(
        "obs_states", lambda device, obsStates: device._obs_state in obsStates
    )
    device_check.register(
        "is_obs",  # shortcut for most common case
        lambda device, obsStates: device.get_state() == DevState.ON
        and device._admin_mode in [AdminMode.ONLINE, AdminMode.MAINTENANCE]
        and device._obs_state in obsStates,
    )

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """
        Initialises the attributes and properties of the MccsSubarray.
        """
        self.set_state(DevState.INIT)
        super().init_device()
        # push back to DevState.INIT again because we are still
        # initialising, and SKASubarray.init_device() prematurely
        # pushes to  DevState.DISABLE
        self.set_state(DevState.INIT)

        # The standard control models mandates initialising adminMode to
        # its "factory default" of MAINTENANCE, which will usually be
        # overwritten by its memorised value. But subarrays are purely
        # logical devices, and a pool of them is created at start-up,
        # to be used on demand. Therefore the subarray adminMode isi
        # initialised into adminMode OFFLINE, and is NOT memorized.
        self._admin_mode = AdminMode.OFFLINE

        # This next call will eventually be asynchronous
        self.do_init()

    def do_init(self):
        """
        Does the initialisation then sets the State. This
        exists as a separate method because it is the extent of
        initialisation that should eventually become an async method.
        """
        self.initialise_device()
        self.init_completed()

    @device_check(states=[DevState.INIT])
    def init_completed(self):
        if self._admin_mode in [AdminMode.OFFLINE, AdminMode.NOT_FITTED]:
            self.set_state(DevState.DISABLE)
        else:
            self.set_state(DevState.OFF)

        self.logger.info("MCCS Subarray device initialised.")

    def initialise_device(self):
        """
        Hook for the asynchronous initialisation code.
        :return: Whether the initialisation was completed successfully.
        :rtype: boolean
        """
        self._scan_id = -1
        self._fqdns = {
            "stations": [],
            "station_beams": [],
            "tiles": [],
        }

        self.set_change_event("stationFQDNs", True, True)
        self.set_archive_event("stationFQDNs", True, True)

        self._build_state = release.get_release_info()
        self._version_id = release.version

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """

    def delete_device(self):
        """
        Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated
        in the init_device() method to be released.  This method is
        called by the device destructor and by the device Init command.
        """

    # ------------------
    # Attribute methods
    # ------------------
    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        doc="The ID of the current scan, set via commands Scan() and "
        "endScan(). A scanId of 0 means that the subarray is idle.",
    )
    def scanId(self):
        """
        Return the scanId attribute.
        """
        return self._scan_id

    @scanId.write
    def scanId(self, id):
        self._scan_id = id

    @attribute(
        dtype=("DevString",),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the "
        "Stations allocated to this Subarray",
    )
    def stationFQDNs(self):
        """
        Return the stationFQDNs attribute.
        """
        return self._fqdns["stations"]

    @stationFQDNs.write
    def stationFQDNs(self, values):
        self._station_FQDNs = values

    @attribute(
        dtype=("DevString",),
        max_dim_x=8192,
        format="%s",
        polling_period=1000,
        doc="Array holding the full qualified device names of the "
        "Tiles allocated to this Subarray",
    )
    def tileFQDNs(self):
        """
        Return the tileFQDNs attribute.
        """
        return self._fqdns["tiles"]

    @tileFQDNs.write
    def tileFQDNs(self, values):
        self._tile_FQDNs = values

    @attribute(
        dtype=("DevString",),
        max_dim_x=512,
        format="%s",
        polling_period=1000,
        doc="Array holding the fully qualified device names of the "
        "Station Beams allocated to this Subarray",
    )
    def stationBeamFQDNs(self):
        """
        Return the stationBeamFQDNs attribute.
        """
        return self._fqdns["station_beams"]

    @stationBeamFQDNs.write
    def stationBeamFQDNs(self, values):
        self._station_beam_FQDNs = values

    # -------------------------------------
    # Base class attribute method overrides
    # -------------------------------------
    @attribute(
        dtype=AdminMode,
        doc="The admin mode reported for this device. It may interpret "
        "the current device condition and condition of all managed "
        "devices to set this.",
    )
    def adminMode(self):
        return super().read_adminMode()

    @adminMode.write
    def adminMode(self, value):
        """
        Write the new adminMode value. Used by TM to put the subarray
        online and to take it offline. This action triggers further
        actions and state changes as follows:

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

        #. The subarray can change between ONLINE and MAINTENANCE at any
           time, with no further change to the state machine. The
           subarray simply changes from a "science subarray" to an
           "engineering subarray" (or vice versa) and continues on with
           whatever it was doing.

        #. The subarray can be taken OFFLINE or put into NOT_FITTED mode
           at any time, in which case it aborts whatever it was doing,
           deconfigures, releases its resources, and changes State to
           DISABLED.

        #. When the subarray is placed into ONLINE or MAINTENANCE mode
           from OFFLINE or NOT_FITTED mode, the subarray is being put
           online, so the state changes from DISABLE to OFF.

        :param value: the new admin mode
        :type value: AdminMode enum value
        """
        enabling_modes = [AdminMode.ONLINE, AdminMode.MAINTENANCE]
        disabling_modes = [AdminMode.OFFLINE, AdminMode.NOT_FITTED]

        state = self.get_state()
        if state == DevState.DISABLE and value in enabling_modes:
            # This write must enable the subarray
            self.set_state(DevState.OFF)
        elif state in [DevState.OFF, DevState.ON] and value in disabling_modes:
            # This write must disable the subarray
            if state == DevState.ON:
                self.Reset()
                self.ReleaseAllResources()
            self.set_state(DevState.DISABLE)
        # super().write_adminMode(value)
        self._admin_mode = value

    # -------------------------------------------
    # Base class command and gatekeeper overrides
    # -------------------------------------------
    @device_check(
        admin_modes=[AdminMode.ONLINE, AdminMode.MAINTENANCE],
        states=[DevState.OFF, DevState.ON],
        obs_states=[ObsState.IDLE]
    )
    def is_AssignResources_allowed(self):
        """
        Check whether command AssignResources() is permitted in this devic
        state.

        Probably don't need to override this -- the base class implementation
        is sound -- but doing so for the sake of completeness.
        """
        return True  # but see decorator

    @command(
        dtype_in='str',
        doc_in="JSON string describing resources to be added to this subarray",
        dtype_out='DevVarStringArray',
        doc_out="[ReturnCode, information-only string]"
    )
    @json_input()
    def AssignResources(self, **resources):
        """
        Assign some resources.

        Overriding to reimplement

        :param argin: a string JSON-encoding of a dictionary containing
            the following optional key-value entries:
            * stations:  a list of station FQDNs
            * station_beams:  a list of station beam FQDNs
            * tiles: a list of tile FQDNs
        :type argin: str
        """
        for resource in resources:
            current = set(self._fqdns[resource])
            to_assign = set(resources[resource])

            if not current.isdisjoint(to_assign):
                Except.throw_exception(
                    "API_CommandFailed",
                    "Cannot assign {} already assigned: {}".format(
                        resource,
                        ", ".join(to_assign & current)
                    ),
                    "MccsSubarray.AssignResources()",
                    ErrSeverity.ERR
                )

        for resource in resources:
            current = set(self._fqdns[resource])
            to_assign = set(resources[resource])

            self._fqdns[resource] = sorted(current | to_assign)

        if any(self._fqdns.values()):
            self.set_state(DevState.ON)
        return [ReturnCode.OK.name, "AssignResources command completed"]

#     @command()
#     def AssignResources(self):  # , jstr):
#         stations = [
#             {
#                 "fqdn": "mccs/station/01",
#                 "beams": ["mccs/beam/03", "mccs/beam/04"],
#                 "tiles": ["mccs/tile/04", "mccs/tile/05", "mccs/tile/06"],
#             },
#             {
#                 "fqdn": "mccs/station/02",
#                 "beams": ["mccs/beam/01", "mccs/beam/02"],
#                 "tiles": ["mccs/tile/01", "mccs/tile/02", "mccs/tile/03"],
#             },
#         ]
#         #        stations = json.loads(jstr)
#         for station in stations:
#             proxy = DeviceProxy(station.get("fqdn"))
#             proxy.tileFQDNs = station.get("tiles")
#             proxy.stationBeamFqdns = station.get("beams")
#             proxy.subarrayId = self._scan_id
#             proxy.command_inout("CreateStation")

    @device_check(is_obs=[ObsState.IDLE])
    def is_ReleaseResources_allowed(self):
        """
        Check whether command ReleaseResources() is permitted in this device state.

        Overriding because base class allows releasing of resources when the
        subarray is in OFF state (i.e. it is already empty).
        """
        return True  # but see decorator

    @command(
        dtype_in='str',
        doc_in="JSON string describing resources to be removed from subarray.",
        dtype_out='DevVarStringArray',
        doc_out="[ReturnCode, information-only string]"
    )
    @json_input()
    def ReleaseResources(self, **resources):
        """
        Release some resources.

        Overriding in reimplement, and in order to set state back to OFF
        if array has been emptied.
        """
        for resource in resources:
            current = set(self._fqdns[resource])
            to_release = set(resources[resource])

            if not current >= to_release:
                Except.throw_exception(
                    "API_CommandFailed",
                    "Cannot release {} not assigned: {}".format(
                        resource,
                        ", ".join(to_release - current)
                    ),
                    "MccsSubarray.ReleaseResources()",
                    ErrSeverity.ERR
                )

        for resource in resources:
            current = set(self._fqdns[resource])
            to_release = set(resources[resource])
            self._fqdns[resource] = sorted(current - to_release)

        if not any(self._fqdns.values()):
            self.set_state(DevState.OFF)

        return [ReturnCode.OK.name, "ReleaseResources command completed"]

    @device_check(is_obs=[ObsState.IDLE])
    def is_ReleaseAllResources_allowed(self):
        """
        Overriding because base class allows releasing of resources when the
        subarray is in OFF state (i.e. it is already empty).
        """
        return True  # but see decorator

    @command(
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]"
    )
    @DebugIt()
    def ReleaseAllResources(self):
        """
        Release all resources.

        Overriding to reimplement, and in order to set state back to OFF
        """
        for resource in self._fqdns:
            self._fqdns[resource].clear()
        self.set_state(DevState.OFF)
        return [ReturnCode.OK.name, "ReleaseAllResources command completed."]

    @device_check(is_obs=[ObsState.IDLE, ObsState.READY])
    def is_ConfigureCapability_allowed(self):
        """
        Check whether command ConfigureCapability is permitted in this
        device state.

        Overriding because base class requires device to be in adminMode
        ONLINE, whereas it should also be possible to configure
        capabilities while in adminMode=MAINTENANCE.
        """
        return True  # but see decorator

    @command(
        dtype_in="DevVarLongStringArray",
        doc_in="[Number of instances to add][Capability types]",
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]",
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

        # This next call will eventually be asynchronous
        self._do_configure(argin)

        # Once this is asynchronous, we will
        # return ["STARTED", "ConfigureCapability started"]
        return [ReturnCode.OK.name, "ConfigureCapability executed synchronously"]

    def _do_configure(self, argin):
        """
        Does the configuration then sets the obsState to READY. This
        exists as a separate method because it is the extent of
        configuration that should eventually become an async method.
        """
        if self._configure(argin):
            self._configure_completed()

    @device_check(is_obs=[ObsState.CONFIGURING])
    def _configure_completed(self):
        self._obs_state = ObsState.READY

    def _configure(self, argin):
        """
        Hook for the asynchronous configuration code.
        :return: Whether the configuration was completed successfully.
        :rtype: boolean
        """
        return True

    @device_check(is_obs=[ObsState.READY])
    def is_DeconfigureCapability_allowed(self):
        """
        Check whether command DeconfigureCapability() is permitted in
        this device state.

        Overriding because base class permits this to run in obsState
        IDLE, when it has no configured capabilities to deconfigure, and
        because it disallows it in adminMode MAINTENANCE.
        """
        return True  # but see decorator

    @command(
        dtype_in="DevVarLongStringArray",
        doc_in="[Number of instances to remove][Capability types]",
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    @DebugIt()
    def DeconfigureCapability(self, argin):
        """
        Deconfigure one or more instances of one or more capabilities.

        Overriding to ensure device ends up in the right state.
        """
        super().DeconfigureCapability(argin)
        if not any(self._configured_capabilities.values()):
            self._obs_state = ObsState.IDLE

        return [ReturnCode.OK.name, "DeconfigureCapability command completed"]

    @device_check(is_obs=[ObsState.READY])
    def is_DeconfigureAllCapabilities_allowed(self):
        """
        Check whether command DeconfigureAllCapabilities() is permitted
        in this device state.

        Overriding because base class permits this to run in obsState
        IDLE, when it has no configured capabilities to deconfigure, and
        because it disallows it in adminMode MAINTENANCE.
        """
        return True  # but see decorator

    @command(
        dtype_in="str",
        doc_in="Capability type",
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    @DebugIt()
    def DeconfigureAllCapabilities(self, argin):
        """
        Deconfigure all instances of a given capability type.

        Overriding to ensure device ends up in the right state.
        """
        super().DeconfigureAllCapabilities(argin)
        if not any(self._configured_capabilities.values()):
            self._obs_state = ObsState.IDLE
        return [ReturnCode.OK.name, "DeconfigureAllCapabilities command completed"]

    @device_check(is_obs=[ObsState.READY])
    def is_Scan_allowed(self):
        """
        Check device state to confirm that command `Scan()` is allowed.
        """
        return True  # but see decorator

    @command(
        dtype_in=("str",),
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    def Scan(self, argin):
        """
        Start scanning.

        Overriding in order to set obsState to SCANNING.
        """
        super().Scan(argin)
        self._obs_state = ObsState.SCANNING

        # This next call will eventually be asynchronous
        self._do_scan(argin)

        return [ReturnCode.STARTED.name, "Scan command started"]

    def _do_scan(self, argin):
        """
        Does the scan then sets the obsState to READY. This
        exists as a separate method because it comprises that part of
        the scan command that will eventually be done asynchtonously.
        """
        if self._scan(argin):
            self._scan_completed()

    @device_check(is_obs=[ObsState.SCANNING])
    def _scan_completed(self):
        self._obs_state = ObsState.READY

    def _scan(self, argin):
        """
        Hook for the asynchronous scan code.
        :return: Whether the scan completed successfully. If true, then
        the device will transition from SCANNING to READY. If False,
        it is assumed that something else occurred (such as an Abort()
        or an EndScan(), and that that something else will handle the
        device state, so no state transition occurs.
        :rtype: boolean
        """
        # For this synchronous version of the code, we don't want the
        # scan to complete, we want it to remain SCANNING until we
        # interrupt it, for example with EndScan() or Abort().
        return False

    @device_check(is_obs=[ObsState.SCANNING])
    def is_EndScan_allowed(self):
        """
        Check device state to confirm that command `EndScan()` is
        allowed.
        """
        return True  # but see decorator

    @command(
        dtype_out="DevVarStringArray", doc_out="[ReturnCode, information-only string]"
    )
    @DebugIt()
    def EndScan(self):
        """
        Ends the scan.

        Overriding in order to set obsState to READY.
        """
        super().EndScan()
        self._obs_state = ObsState.READY
        return [ReturnCode.OK.name, "EndScan command completed"]

    @device_check(is_obs=[ObsState.READY])
    def is_EndSB_allowed(self):
        """
        Check device state to confirm that command `EndSB()` is allowed.
        """
        return True  # but see decorator

    @command(
        dtype_out="DevVarStringArray", doc_out="[ReturnCode, information-only string]"
    )
    @DebugIt()
    def EndSB(self):
        """
        Signals the end of the scanblock.

        Overriding in order to change obsState to IDLE
        """
        super().EndSB()
        self._obs_state = ObsState.IDLE
        return [ReturnCode.OK.name, "EndSB command completed"]

    @device_check(is_obs=[ObsState.CONFIGURING, ObsState.READY, ObsState.SCANNING])
    def is_Abort_allowed(self):
        """
        Check device state to confirm that command `Abort()` is allowed.
        """
        return True  # but see decorator

    @command(
        dtype_out="DevVarStringArray", doc_out="[ReturnCode, information-only string]"
    )
    @DebugIt()
    def Abort(self):
        """
        Abort the scan.

        Overriding in order to set obsState to ABORTED.
        """
        super().Abort()
        self._obs_state = ObsState.ABORTED
        return [ReturnCode.OK.name, "Abort command completed"]

    @device_check(
        is_obs=[
            ObsState.CONFIGURING,
            ObsState.READY,
            ObsState.SCANNING,
            ObsState.ABORTED,
        ]
    )
    def is_Reset_allowed(self):
        """
        Check whether Reset() is allowed in this device state

        Overriding because base class allows reset at any time, whereas
        this command seems to be defined for subarrays as 'stop what
        you're doing and deconfigure but don't release your resources.'
        This semantics only makes sense when we are in ON state with an
        obsState not IDLE.
        """
        return True  # but see decorator

    @command(
        dtype_out="DevVarStringArray", doc_out="[ReturnCode, information-only string]"
    )
    @DebugIt()
    def Reset(self):
        """
        Reset the scan

        Overriding in order to conform to state machine
        """

        if self.get_state() == DevState.ON:
            # abort any configuring or running scan
            # deconfigure
            self._obs_state = ObsState.IDLE
        return [ReturnCode.OK.name, "Reset command completed"]

    def is_Pause_allowed(self):
        """
        Returns False, because Pause command has been removed, but at
        present it is still implemented in the base classes.
        """
        return False

    def is_Resume_allowed(self):
        """
        Returns False, because Resume command has been removed, but at
        present it is still implemented in the base classes.
        """
        return False

    # ---------------------
    # MccsSubarray Commands
    # ---------------------

    @command(
        dtype_in="DevVarLongArray",
        doc_in="Specification of the segment of the transient buffer "
        "to send, comprising:"
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
        # dtype_out="DevString",
        # doc_out="ASCII string that indicates status, for information "
        # "purposes only",
        dtype_out="DevVarStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    @DebugIt()
    def sendTransientBuffer(self, argin):
        """
        Cause the subarray to send the requested segment of the
        transient buffer to SDP. The requested segment is specified by:

        1. Start time (timestamp: milliseconds since UNIX epoch)
        2. End time (timestamp: milliseconds since UNIX epoch)
        3. Dispersion measure

        Together, these parameters narrow the selection of transient
        buffer data to the period of time and frequencies that are of
        interest.

        Additional metadata, such as the ID of a triggering Scheduling
        Block, may need to be supplied to allow SDP to assign data
        ownership correctly (TBD75).

        :todo: This method is a stub that does nothing but return a
            dummy string.
        :param argin: Specification of the segment of the transient
            buffer to send
        :type argin: DevVarLongArray
        :return: ASCII String that indicates status, for information
            purposes only
        :rtype: DevString
        """
        return [ReturnCode.OK.name, "sendTransientBuffer command completed"]


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
