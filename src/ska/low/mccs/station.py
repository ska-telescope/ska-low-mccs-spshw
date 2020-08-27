# -*- coding: utf-8 -*-
#
# This file is part of the MccsStation project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MCCS Station

MccsStation is the Tango device class for the MCCS Station prototype.
"""
__all__ = ["MccsStation", "main"]

import threading

# PyTango imports
import tango
from tango import DebugIt, DevState
from tango.server import device_property
from tango.server import attribute, command

# additional imports
from ska.base import SKAObsDevice
from ska.base.commands import ResponseCommand, ResultCode

# from ska.low.mccs import MccsGroupDevice
import ska.low.mccs.release as release
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthMonitor, RollupPolicy


class MccsStation(SKAObsDevice):
    """
    MccsStation is the Tango device class for the MCCS Station prototype.

    **Properties:**

    - Device Property
        StationId
            - MCCS station ID for this station
            - Type: int (scalar attribute)
        TileFQDNs
            - List of Tile FQDNs (Fully Qualified Domain Name)
            - Type: str (spectrum attribute)
    """

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    TileFQDNs = device_property(dtype=(str,))
    AntennaFQDNs = device_property(dtype=(str,))

    # ---------------
    # General methods
    # ---------------

    class InitCommand(SKAObsDevice.InitCommand):
        """
        Class that implements device initialisation for the MCCS Tile
        State is managed under the hood; the basic sequence is:

        1. Device state is set to INIT
        2. The do() method is run
        3. Device state is set to the appropriate outgoing state,
           usually off

        """

        def do(self):
            """Initialises the attributes and properties of the MccsStation."""
            super().do()
            device = self.target
            device._subarray_id = 0
            device._tile_fqdns = list(device.TileFQDNs)
            device._antenna_fqdns = list(device.AntennaFQDNs)
            device._beam_fqdns = []
            device._transient_buffer_fqdn = ""
            device._delay_centre = []
            device._calibration_coefficients = []
            device._is_calibrated = False
            device._is_configured = False
            device._calibration_job_id = 0
            device._daq_job_id = 0
            device._data_directory = ""

            device._build_state = release.get_release_info()
            device._version_id = release.version
            device._station_id = device.StationId

            device.set_change_event("subarrayId", True, True)
            device.set_archive_event("subarrayId", True, True)
            device.set_change_event("tileFQDNs", True, True)
            device.set_archive_event("tileFQDNs", True, True)
            device.set_change_event("beamFQDNs", True, True)
            device.set_archive_event("beamFQDNs", True, True)
            device.set_change_event("transientBufferFQDN", True, False)
            device.set_archive_event("transientBufferFQDN", True, False)
            device.set_change_event("healthState", True, True)
            device.set_archive_event("healthState", True, True)
            device._lock = threading.Lock()

            # initialise the health table using the FQDN as the key.
            # Create and event manager per FQDN and subscribe to events from it
            device._eventManagerList = []
            fqdns = device._tile_fqdns + device._antenna_fqdns  # + device._beam_fqdns
            device._rollup_policy = RollupPolicy(device.update_healthstate)
            device._health_monitor = HealthMonitor(
                fqdns, device._rollup_policy.rollup_health
            )

            for fqdn in device._tile_fqdns:
                device._eventManagerList.append(
                    EventManager(fqdn, device._health_monitor.update_health_table)
                )
            for fqdn in device._antenna_fqdns:
                device._eventManagerList.append(
                    EventManager(fqdn, device._health_monitor.update_health_table)
                )
            # for fqdn in device._beam_fqdns:
            #     device._eventManagerList.append(
            #         EventManager(fqdn, device._health_monitor.update_health_table)
            #     )

            return (ResultCode.OK, "Station Init complete")

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """
        state = self.get_state()
        if self._is_calibrated and self._is_configured:
            if state == DevState.ALARM:
                self.set_state(DevState.ON)
        else:
            if state == DevState.ON:
                self.set_state(DevState.ALARM)

    def delete_device(self):
        """
        Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        for event_manager in self._eventManagerList:
            event_manager.unsubscribe()
        self._eventManagerList = None

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype="DevLong",
        format="%i",
        max_value=512,
        min_value=0,
        doc="The ID of this Station",
    )
    def stationId(self):
        """
        Return the stationId attribute.
        """
        return self._station_id

    @attribute(
        dtype="DevLong",
        format="%i",
        max_value=16,
        min_value=0,
        doc="The ID of the Subarray to which this Station is allocated",
    )
    def subarrayId(self):
        """
        Return the subarrayId attribute.
        """
        return self._subarray_id

    @subarrayId.write
    @DebugIt()
    def subarrayId(self, id):
        """
        Set the ID of the Subarray to which this Station is allocated
        Note: ID propogates to each tile in this station too
        """
        self._subarray_id = id
        for fqdn in self._tile_fqdns:
            tile = tango.DeviceProxy(fqdn)
            tile.subarrayId = id

    @attribute(
        dtype="DevString",
        format="%s",
        doc="The fully-qualified device name of the 'transient buffer' "
        "TANGO device created by the Station",
    )
    def transientBufferFQDN(self):
        """
        Return the transientBufferFQDN attribute.
        """
        return self._transient_buffer_fqdn

    @attribute(
        dtype="DevBoolean",
        doc="Defined whether the calibration cycle was successful "
        "(converged, good phase centres)",
        polling_period=1000,
    )
    def isCalibrated(self):
        """
        Return the isCalibrated attribute.
        """
        return self._is_calibrated

    @isCalibrated.write
    def isCalibrated(self, value):
        self._is_calibrated = value

    @attribute(
        dtype="DevBoolean",
        doc="True when the Station is configured, False when the Station "
        "is unconfigured or in the process of reconfiguring.",
        polling_period=1000,
    )
    def isConfigured(self):
        """
        Return the isConfigured attribute.
        """
        return self._is_configured

    @isConfigured.write
    def isConfigured(self, value):
        self._is_configured = value

    @attribute(
        dtype="DevLong",
        format="%i",
        doc="The job ID for calibration jobs submitted by this Station",
    )
    def calibrationJobId(self):
        """
        Return the calibrationJobId attribute.
        """
        return self._calibration_job_id

    @attribute(
        dtype="DevLong",
        format="%i",
        doc="The job ID for DAQ jobs submitted by this Station.",
    )
    def daqJobId(self):
        """
        Return the daqJobId attribute.
        """
        return self._daq_job_id

    @attribute(
        dtype="DevString",
        format="%s",
        doc="Parent directory for all files generated by the station.",
    )
    def dataDirectory(self):
        """
        Return the dataDirectory attribute.
        """
        return self._data_directory

    @attribute(
        dtype=("DevString",),
        max_dim_x=16,
        format="%s",
        doc="Array of fully-qualified device names of the Tile devices that "
        "are associated with the Station",
    )
    def tileFQDNs(self):
        """
        Return the tileFQDNs attribute.
        """
        return self._tile_fqdns

    @attribute(
        dtype=("DevString",),
        max_dim_x=8,
        format="%s",
        doc="Array of full-qualified device names for the Station Beams "
        "associated with this Station",
    )
    def beamFQDNs(self):
        """
        Return the beamFQDNs attribute.
        """
        return self._beam_fqdns

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        doc="""WGS84 position of the delay centre of the Station.
        :todo: WGS84is a datum. What is the coordinate system?: Latitude and
        longitude? Or is it SUTM50 eastings and northings? Either way, do we
        need to allow for elevation too?""",
    )
    def delayCentre(self):
        """
        Return the delayCentre attribute.
        """
        return self._delay_centre

    @delayCentre.write
    def delayCentre(self, value):
        """
        Set the delayCentre attribute.
        """
        self._delay_centre = value

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=512,
        doc="""Latest calibration coefficients for the station (split per
        channel/antenna)
        :todo: How big should this array be? Gain and offset per antenna per
        channel. This station can have up to 16 tiles of up to 16 antennas, so
        that is 2 x 16 x 16 = 512 coefficients per channel. But how many
        channels?""",
    )
    def calibrationCoefficients(self):
        """
        Return the calibrationCoefficients attribute.
        """
        return self._calibration_coefficients

    # --------
    # Commands
    # --------
    def init_command_objects(self):
        """
        Set up the handler objects for Commands
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)

        self.register_command_object("Configure", self.ConfigureCommand(*args))

    class ConfigureCommand(ResponseCommand):
        """
        Class for handling the Configure() command.
        """

        def do(self):
            device = self.target
            for id, tile in enumerate(device.TileFQDNs):
                proxy = tango.DeviceProxy(tile)
                proxy.subarrayId = device._subarray_id
                proxy.stationId = device._station_id
                proxy.logicalTileId = id + 1
                proxy.command_inout("Connect", True)

            #             self._beams = []
            #             for id, beam in enumerate(self._beam_fqdns):
            #                 proxy = tango.DeviceProxy(beam)
            #                 self._beam.append(proxy)
            #                 proxy.stationId = self.StationId
            #                 proxy.logicalBeamId = id + 1
            #                 print(proxy)
            #                 print(f"beamId {proxy.beamId}")
            #                 print(f"logicalBeamId {proxy.logicalBeamId}")

            device._is_configured = True
            return (ResultCode.OK, "Command succeeded")

    @command(
        dtype_out="DevVarLongStringArray",
        doc_out="(ResultCode, 'informational message')",
    )
    def Configure(self):
        """
        Configure the station with tiles

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("Configure")
        """
        handler = self.get_command_object("Configure")
        (return_code, message) = handler()
        return [[return_code], [message]]

    def update_healthstate(self, health_state):
        self.push_change_event("healthState", health_state)
        with self._lock:
            self._health_state = health_state
        print("health state=", health_state)


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """Main function of the MccsStation module."""

    return MccsStation.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
