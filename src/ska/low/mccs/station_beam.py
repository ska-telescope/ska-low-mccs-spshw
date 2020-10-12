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

# imports

# PyTango imports
from tango import DevState
from tango.server import attribute
from tango.server import device_property

# Additional imports
from ska.base import SKAObsDevice
from ska.base.commands import ResultCode
from ska.base.control_model import HealthState
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
            Initialises the attributes and properties of the
            `MccsStationBeam`.

            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to the OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
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
            device._is_beam_locked = False

            device._build_state = release.get_release_info()
            device._version_id = release.version

            message = "MccsStationBeam Init command completed OK"
            self.logger.info(message)
            return (ResultCode.OK, message)

    def always_executed_hook(self):
        """
        Method always executed before any TANGO command is executed.
        """
        if self._is_beam_locked:
            self._health_state = HealthState.OK
        else:
            self._health_state = HealthState.DEGRADED

        state = self.get_state()
        if self._health_state == HealthState.OK:
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

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="DevLong", format="%i", polling_period=1000, doc="ID of the beam")
    def beamId(self):
        """
        Return the beam id

        :return: the beam id
        :rtype: int
        """
        return self._beam_id

    @attribute(dtype="DevLong", format="%i", doc="ID of the associated station")
    def stationId(self):
        """
        Return the station id

        :return: the station id
        :rtype: int
        """
        return self._station_id

    @stationId.write
    def stationId(self, station_id):
        """
        Set the station id

        :param station_id: id of the station for this beam
        :type station_id: int
        """
        self._station_id = station_id

    @attribute(
        dtype="DevLong",
        format="%i",
        max_value=7,
        min_value=0,
        doc="Logical ID of the beam within the associated Station",
    )
    def logicalBeamId(self):
        """
        Return the logical beam id

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        :rtype: int
        """
        return self._logical_beam_id

    @logicalBeamId.write
    def logicalBeamId(self, logical_beam_id):
        """
        Set the logical beam id

        :param logical_beam_id: the logical beam id
        :type logical_beam_id: int
        """
        self._logical_beam_id = logical_beam_id

    @attribute(
        dtype="DevDouble",
        unit="Hz",
        standard_unit="s^-1",
        max_value=1e37,
        min_value=0,
        doc="The update rate in Hz to use when updating pointing coefficients",
    )
    def updateRate(self):
        """
        Return the update rate (in hertz) for this station beam

        :return: the update rate for this station beam
        :rtype: double
        """
        return self._update_rate

    @attribute(
        dtype="DevBoolean",
        doc="Flag specifying whether beam is locked to target",
        polling_period=1000,
    )
    def isBeamLocked(self):
        """
        Return a flag indicating whether the beam is locked or not

        :return: whether the beam is locked or not
        :rtype: bool
        """
        return self._is_beam_locked

    @isBeamLocked.write
    def isBeamLocked(self, value):
        """
        Set a flag indicating whether the beam is locked or not

        :param value: whether the beam is locked or not
        :type value: boolean
        """
        self._is_beam_locked = value

    @attribute(
        dtype=("DevLong",),
        max_dim_x=384,
        doc="The channel configuration for the Station Beam, specified as an "
        "array of channel IDs (where the lowest frequency is "
        "(channelID+1)*781250 Hz). When the Station Beam is OFF, the array is"
        " empty.",
    )
    def channels(self):
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        :rtype: array of int
        """
        return self._channels

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=4,
        doc="An array of doubles conforming to the Sky Coordinate Set "
        "definition. It comprises:"
        "* activation time (s) -- value range 0-10^37"
        "* azimuth position (deg) -- value range 0-360"
        "* elevation position (deg) -- value range 0-90"
        "* azimuth speed (deg/s) -- value range 0-10^37",
    )
    def desiredPointing(self):
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam
        :rtype: array of doubles conforming to the Sky Coordinate Set
            definition
        """
        return self._desired_pointing

    @desiredPointing.write
    def desiredPointing(self, value):
        """
        Set the desired pointing of this beam

        :param value: the desired pointing of this beam
        :type value: array of doubles conforming to the Sky Coordinate
            Set definition
        """
        self._desired_pointing = value

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Latest computed pointing delay per antenna",
    )
    def pointingDelay(self):
        """
        Return the pointing delay per antenna

        :return: the pointing delay per antenna
        :rtype: array of double
        """
        return self._pointing_delay

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Latest computed pointing delay rate per antenna",
    )
    def pointingDelayRate(self):
        """
        Return the pointing delay rate for each antenna

        :return: the pointing delay rate per antenna
        :rtype: array of double
        """
        return self._pointing_delay_rate

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Defines the contribution of each antenna to the station beam to "
        "give a desired beam shape, e.g. to suppress sidelobs",
    )
    def antennaWeights(self):
        """
        Return the antenna weights

        :return: the antenna weights
        :rtype: array of double
        """
        return self._antenna_weights

    @antennaWeights.write
    def antennaWeights(self, value):
        """
        Set the antenna weights

        :param value: the new antenna weights
        :type value: array of double
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
    Main function of the :py:mod:`ska.low.mccs.station_beam` module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsStationBeam.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
