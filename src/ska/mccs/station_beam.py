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
# import tango
# from tango import DebugIt  # unused because no commands
from tango.server import run
# from tango.server import Device, DeviceMeta
from tango.server import attribute  # , command # unused
# from tango.server import device_property  # unused
# from tango import AttrQuality, DispLevel  # unused
from tango import DevState
from tango import AttrWriteType
# from tango import PipeWriteType  # unused
# import enum  # unused

# Additional imports
from ska.base import SKAObsDevice
import ska.mccs.release as release


class MccsStationBeam(SKAObsDevice):
    """
    Prototype TANGO device server for the MCSS Station Beam

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    stationId = attribute(
        dtype='DevLong',
        format="%i",
        polling_period=1000,
        doc="ID of the associated station",
    )

    logicalId = attribute(
        dtype='DevLong',
        format="%i",
        polling_period=1000,
        max_value=7,
        min_value=0,
        doc="Logical ID of the beam within the associated Station",
    )

    updateRate = attribute(
        dtype='DevDouble',
        unit="Hz",
        standard_unit="s^-1",
        polling_period=1000,
        max_value=1e37,
        min_value=0,
        doc="The update rate in Hz to use when updating pointing coefficients",
    )

    isLocked = attribute(
        dtype='DevBoolean',
        polling_period=1000,
        doc="Flag specifying whether beam is locked to target",
    )

    channels = attribute(
        dtype=('DevLong',),
        max_dim_x=384,
        polling_period=1000,
        doc="The channel configuration for the Station Beam, specified as an "
        "array of channel IDs (where the lowest frequency is "
        "(channelID+1)*781250 Hz). When the Station Beam is OFF, the array is"
        " empty.",
    )

    desiredPointing = attribute(
        dtype=('DevDouble',),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=4,
        polling_period=1000,
        doc="An array of doubles conforming to the Sky Coordinate Set "
        "definition. It comprises:"
        "* activation time (s) -- value range 0-10^37"
        "* azimuth position (deg) -- value range 0-360"
        "* elevation position (deg) -- value range 0-90"
        "* azimuth speed (deg/s) -- value range 0-10^37",
    )

    pointingDelay = attribute(
        dtype=('DevDouble',),
        max_dim_x=256,
        polling_period=1000,
        doc="Latest computed pointing delay per antenna",
    )

    pointingDelayRate = attribute(
        dtype=('DevDouble',),
        max_dim_x=256,
        polling_period=1000,
        doc="Latest computed pointing delay rate per antenna",
    )

    antennaWeights = attribute(
        dtype=('DevDouble',),
        access=AttrWriteType.READ_WRITE,
        max_dim_x=256,
        polling_period=1000,
        doc="Defines the contribution of each antenna to the station beam to "
        "give a desired beam shape, e.g. to suppress sidelobs",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """
        Initialises the attributes and properties of the MccsStationBeam.
        """
        SKAObsDevice.init_device(self)

        self.set_state(DevState.INIT)

        self._station_id = 0
        self._logical_id = 0
        self._channels = []
        self._desired_pointing = []
        self._pointing_delay = []
        self._pointing_delay_rate = []
        self._update_rate = 0
        self._antenna_weights = []
        self._is_locked = False

        self._build_state = release.get_release_info()
        self._version_id = release.version

        self.set_change_event("stationId", True, True)
        self.set_archive_event("stationId", True, True)
        self.set_change_event("logicalId", True, True)
        self.set_archive_event("logicalId", True, True)
        self.set_change_event("updateRate", True, True)
        self.set_archive_event("updateRate", True, True)
        self.set_change_event("isLocked", True, True)
        self.set_archive_event("isLocked", True, True)
        self.set_change_event("channels", True, True)
        self.set_archive_event("channels", True, True)

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

    # ------------------
    # Attributes methods
    # ------------------

    def read_stationId(self):
        """
        Return the stationId attribute.
        """
        return self._station_id

    def read_logicalId(self):
        """
        Return the logicalId attribute.
        """
        return self._logical_id

    def read_updateRate(self):
        """
        Return the updateRate attribute.
        """
        return self._update_rate

    def read_isLocked(self):
        """
        Return the isLocked attribute.
        """
        return self._is_locked

    def read_channels(self):
        """
        Return the channels attribute.
        """
        return self._channels

    def read_desiredPointing(self):
        """
        Return the desiredPointing attribute.
        """
        return self._desired_pointing

    def write_desiredPointing(self, value):
        """
        Set the desiredPointing attribute.
        """
        self._desired_pointing = value

    def read_pointingDelay(self):
        """
        Return the pointingDelay attribute.
        """
        return self._pointing_delay

    def read_pointingDelayRate(self):
        """
        Return the pointingDelayRate attribute.
        """
        return self._pointing_delay_rate

    def read_antennaWeights(self):
        """
        Return the antennaWeights attribute.
        """
        return self._antenna_weights

    def write_antennaWeights(self, value):
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
    """
    Main function of the MccsStationBeam module.i
    """
    return run((MccsStationBeam,), args=args, **kwargs)


if __name__ == '__main__':
    main()