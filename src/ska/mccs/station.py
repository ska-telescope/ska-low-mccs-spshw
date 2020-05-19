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

# PyTango imports
from tango.server import attribute, command
from tango import DevState
from tango import DeviceProxy
from tango.server import device_property

# additional imports
from ska.base import SKAObsDevice
from ska.mccs import MccsGroupDevice
import ska.mccs.release as release


class MccsStation(SKAObsDevice, MccsGroupDevice):
    """
    MccsStation is the Tango device class for the MCCS Station prototype.

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """
        Initialises the attributes and properties of the MccsStation.
        """
        super().init_device()

        self.set_state(DevState.INIT)

        self._subarray_id = 0
        self._tile_fqdns = []
        self._beam_fqdns = []
        self._transient_buffer_fqdn = ""
        self._delay_centre = []
        self._calibration_coefficients = []
        self._is_calibrated = False
        self._is_configured = False
        self._calibration_job_id = 0
        self._daq_job_id = 0
        self._data_directory = ""

        self._build_state = release.get_release_info()
        self._version_id = release.version

        self.set_change_event("subarrayId", True, True)
        self.set_archive_event("subarrayId", True, True)
        self.set_change_event("transientBufferFQDN", True, False)
        self.set_archive_event("transientBufferFQDN", True, False)
        self.set_change_event("isCalibrated", True, True)
        self.set_archive_event("isCalibrated", True, True)
        self.set_change_event("isConfigured", True, True)
        self.set_archive_event("isConfigured", True, True)
        self.set_change_event("tileFQDNs", True, True)
        self.set_archive_event("tileFQDNs", True, True)
        self.set_change_event("beamFQDNs", True, True)
        self.set_archive_event("beamFQDNs", True, True)

        self._station_id = self.StationId
        self.set_state(DevState.OFF)

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
    def subarrayId(self, id):
        self._subarray_id = id

    @attribute(
        dtype="DevString",
        format="%s",
        polling_period=1000,
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
        polling_period=1000,
        doc="Defined whether the calibration cycle was successful "
        "(converged, good phase centres)",
    )
    def isCalibrated(self):
        """
        Return the isCalibrated attribute.
        """
        return self._is_calibrated

    @attribute(
        dtype="DevBoolean",
        polling_period=1000,
        doc="True when the Station is configured, False when the Station "
        "is unconfigured or in the process of reconfiguring.",
    )
    def isConfigured(self):
        """
        Return the isConfigured attribute.
        """
        return self._is_configured

    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
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
        polling_period=1000,
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
        polling_period=1000,
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

    @tileFQDNs.write
    def tileFQDNs(self, fqdns):
        self._tile_fqdns = fqdns

    @attribute(
        dtype=("DevString",),
        max_dim_x=8,
        format="%s",
        polling_period=1000,
        doc="Array of full-qualified device names for the Station Beams "
        "associated with this Station",
    )
    def beamFQDNs(self):
        """
        Return the beamFQDNs attribute.
        """
        return self._beam_fqdns

    @beamFQDNs.write
    def beamFQDNs(self, fqdns):
        self._beam_fqdns = fqdns

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        polling_period=1000,
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
        polling_period=1000,
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

    @command()
    def CreateStation(self):
        self._tiles = []
        for id, tile in enumerate(self._tile_fqdns):
            proxy = DeviceProxy(tile)
            self._tiles.append(proxy)
            proxy.stationId = self.StationId
            proxy.logicalTileId = id + 1
            self.AddMember(tile)
            print(proxy)
            print(f"tileId {proxy.TileId}")
            print(f"logicalTpmId {proxy.logicalTileId}")
            proxy.command_inout("Connect", True)
            print(proxy.adcPower)
            print(proxy.command_inout("GetRegisterList"))
        self._beams = []
        for id, beam in enumerate(self._beam_fqdns):
            proxy = DeviceProxy(beam)
            self._beam.append(proxy)
            proxy.stationId = self.StationId
            proxy.logicalBeamId = id + 1
            print(proxy)
            print(f"beamId {proxy.beamId}")
            print(f"logicalBeamId {proxy.logicalBeamId}")


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsStation module."""

    return MccsStation.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
