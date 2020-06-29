# -*- coding: utf-8 -*-
#
# This file is part of the MccsStationBeam project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MCCS Station Beam TANGO device prototype

Prototype TANGO device server for the MCSS Station Beam
"""
__all__ = ["MccsStationBeam", "main"]

# PyTango imports
from tango.server import attribute
from tango.server import device_property

# Additional imports
from ska.base import SKAObsDevice
from ska.base.commands import ResultCode
import ska.low.mccs.release as release


class MccsStationBeam(SKAObsDevice):
    """
    Prototype TANGO device server for the MCSS Station Beam

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------
    BeamId = device_property(dtype=int, default_value=0)

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for the MccsStationBeam's init_device() "command".
        """

        def do(self):
            """
            Initialises the attributes and properties of the MccsStationBeam.
            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to the OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (ResultCode, str)
            """
            super().do()

            device = self.target
            device._beam_id = device.BeamId
            device._station_id = 0
            device._logical_beam_id = 0
            device._channels = []
            device._desired_pointing = []
            device._pointing_delay = []
            device._pointing_delay_rate = []
            device._update_rate = 0.0
            device._antenna_weights = []
            device._is_locked = False

            device._build_state = release.get_release_info()
            device._version_id = release.version

            device.set_change_event("stationId", True, True)
            device.set_archive_event("stationId", True, True)
            device.set_change_event("logicalBeamId", True, True)
            device.set_archive_event("logicalBeamId", True, True)
            device.set_change_event("updateRate", True, True)
            device.set_archive_event("updateRate", True, True)
            device.set_change_event("isLocked", True, True)
            device.set_archive_event("isLocked", True, True)
            device.set_change_event("channels", True, True)
            device.set_archive_event("channels", True, True)

            message = "MccsStationBeam Init command completed OK"
            self.logger.info(message)
            return (ResultCode.OK, message)

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

    @attribute(dtype="DevLong", format="%i", polling_period=1000, doc="ID of the beam")
    def beamId(self):
        """
        Return the beamId attribute.
        """
        return self._beam_id

    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        doc="ID of the associated station",
    )
    def stationId(self):
        """
        Return the stationId attribute.
        """
        return self._station_id

    @stationId.write
    def stationId(self, id):
        self._station_id = id

    @attribute(
        dtype="DevLong",
        format="%i",
        polling_period=1000,
        max_value=7,
        min_value=0,
        doc="Logical ID of the beam within the associated Station",
    )
    def logicalBeamId(self):
        """
        Return the logicalBeamId attribute.
        """
        return self._logical_beam_id

    @logicalBeamId.write
    def logicalBeamId(self, id):
        self._logical_beam_id = id

    @attribute(
        dtype="DevDouble",
        unit="Hz",
        standard_unit="s^-1",
        polling_period=1000,
        max_value=1e37,
        min_value=0,
        doc="The update rate in Hz to use when updating pointing coefficients",
    )
    def updateRate(self):
        """
        Return the updateRate attribute.
        """
        return self._update_rate

    @attribute(
        dtype="DevBoolean",
        polling_period=1000,
        doc="Flag specifying whether beam is locked to target",
    )
    def isLocked(self):
        """
        Return the isLocked attribute.
        """
        return self._is_locked

    @attribute(
        dtype=("DevLong",),
        max_dim_x=384,
        polling_period=1000,
        doc="The channel configuration for the Station Beam, specified as an "
        "array of channel IDs (where the lowest frequency is "
        "(channelID+1)*781250 Hz). When the Station Beam is OFF, the array is"
        " empty.",
    )
    def channels(self):
        """
        Return the channels attribute.
        """
        return self._channels

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=4,
        polling_period=1000,
        doc="An array of doubles conforming to the Sky Coordinate Set "
        "definition. It comprises:"
        "* activation time (s) -- value range 0-10^37"
        "* azimuth position (deg) -- value range 0-360"
        "* elevation position (deg) -- value range 0-90"
        "* azimuth speed (deg/s) -- value range 0-10^37",
    )
    def desiredPointing(self):
        """
        Return the desiredPointing attribute.
        """
        return self._desired_pointing

    @desiredPointing.write
    def desiredPointing(self, value):
        """
        Set the desiredPointing attribute.
        """
        self._desired_pointing = value

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        polling_period=1000,
        doc="Latest computed pointing delay per antenna",
    )
    def pointingDelay(self):
        """
        Return the pointingDelay attribute.
        """
        return self._pointing_delay

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        polling_period=1000,
        doc="Latest computed pointing delay rate per antenna",
    )
    def pointingDelayRate(self):
        """
        Return the pointingDelayRate attribute.
        """
        return self._pointing_delay_rate

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        polling_period=1000,
        doc="Defines the contribution of each antenna to the station beam to "
        "give a desired beam shape, e.g. to suppress sidelobs",
    )
    def antennaWeights(self):
        """
        Return the antennaWeights attribute.
        """
        return self._antenna_weights

    @antennaWeights.write
    def antennaWeights(self, value):
        """
        Set the antennaWeights attribute.
        """
        self._antenna_weights = value

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsStationBeam module."""

    return MccsStationBeam.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
