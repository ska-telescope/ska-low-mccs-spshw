# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
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
import json

# PyTango imports
from tango import DevState
from tango.server import attribute, command
from tango.server import device_property

# Additional imports
from ska.base import SKAObsDevice
from ska.base.control_model import HealthState
from ska.base.commands import ResponseCommand, ResultCode
import ska.low.mccs.release as release

from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel


class MccsStationBeam(SKAObsDevice):
    """
    Prototype TANGO device server for the MCCS Station Beam.

    This class is a subclass of :py:class:`ska.base.SKAObsDevice`.

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
        A class for :py:class:`~ska.low.mccs.station_beam.MccsStationBeam`'s Init
        command.
        The :py:meth:`~ska.low.mccs.station_beam.MccsStationBeam.InitCommand.do` method
        below is called upon :py:class:`~ska.low.mccs.station_beam.MccsStationBeam`'s
        initialisation.
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
            :rtype:
                (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            device = self.target
            device._beam_id = device.BeamId
            # Changed station_id to list.
            # This is a divergance from the ICD
            device._station_ids = []
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

            device.event_manager = EventManager()
            device.health_model = HealthModel(None, None, device.event_manager)

            message = "MccsStationBeam Init command completed OK"
            self.logger.info(message)
            return (ResultCode.OK, message)

    def init_command_objects(self):
        """
        Initialises the command handlers for commands supported by this
        device.
        """
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("Configure", self.ConfigureCommand(*args))

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
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.station_beam.MccsStationBeam.InitCommand.do` method of
        the nested :py:class:`~ska.low.mccs.station_beam.MccsStationBeam.InitCommand`
        class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.station_beam.MccsStationBeam.InitCommand.do` method to
        be released. This method is called by the device destructor, and by the Init
        command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------

    # redefinition from base classes to turn polling on
    @attribute(
        dtype=HealthState,
        polling_period=1000,
        doc="The health state reported for this device. "
        "It interprets the current device"
        " condition and condition of all managed devices to set this. "
        "Most possibly an aggregate attribute.",
    )
    def healthState(self):
        """
        returns the health of this device; which in this case means the
        rolled-up health of the entire MCCS subsystem

        :return: the rolled-up health of the MCCS subsystem
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        return self.health_model.health

    @attribute(dtype="DevLong", format="%i", polling_period=1000, doc="ID of the beam")
    def beamId(self):
        """
        Return the beam id

        :return: the beam id
        :rtype: int
        """
        return self._beam_id

    @attribute(
        dtype=("DevLong",),
        max_dim_x=512,
        format="%i",
        doc="IDs of the associated stations",
    )
    def stationIds(self):
        """
        Return the station ids

        :return: the station ids
        :rtype: List[int]
        """
        return self._station_ids

    @stationIds.write
    def stationIds(self, station_ids):
        """
        Set the station ids

        :param station_ids: ids of the stations for this beam
        :type station_ids: List[int]
        """
        self._station_ids = station_ids

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
        :rtype: sequence of int
        """
        return self._channels

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=5,
        doc="An array of doubles conforming to the Sky Coordinate Set "
        "definition. It comprises:"
        "* activation time (s) -- value range 0-10^37"
        "* azimuth position (deg) -- value range 0-360"
        "* azimuth speed (deg/s) -- value range 0-10^37"
        "* elevation position (deg) -- value range 0-90"
        "* elevation rate (deg/s) -- value range 0-10^37",
    )
    def desiredPointing(self):
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam
        :rtype: sequence of doubles conforming to the Sky Coordinate Set
            definition
        """
        return self._desired_pointing

    @desiredPointing.write
    def desiredPointing(self, values):
        """
        Set the desired pointing of this beam
        * activation time (s) -- value range 0-10^37
        * azimuth position (deg) -- value range 0-360
        * azimuth speed (deg/s) -- value range 0-10^37
        * elevation position (deg) -- value range 0-90
        * elevation rate (deg/s) -- value range 0-10^37

        :param values: the desired pointing of this beam
        :type values: sequence of doubles conforming to the Sky
            Coordinate set definition
        """
        self._desired_pointing = values

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Latest computed pointing delay per antenna",
    )
    def pointingDelay(self):
        """
        Return the pointing delay per antenna

        :return: the pointing delay per antenna
        :rtype: sequence of double
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
        :rtype: sequence of double
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
        :rtype: sequence of double
        """
        return self._antenna_weights

    @antennaWeights.write
    def antennaWeights(self, value):
        """
        Set the antenna weights

        :param value: the new antenna weights
        :type value: sequence of double
        """
        self._antenna_weights = value

    # --------
    # Commands
    # --------
    class ConfigureCommand(ResponseCommand):
        """
        Class for handling the Configure(argin) command
        """

        def do(self, argin):
            """
            Stateless do-hook for the
            :py:meth:`MccsStationBeam.Configure`
            command

            :param argin: Configuration specification dict as a json string
            :type argin: json string

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.command.ResultCode`, str)
            """
            config_dict = json.loads(argin)
            device = self.target
            device._station_ids = config_dict.get("station_id")
            device._channels = config_dict.get("channels")
            device._update_rate = config_dict.get("update_rate")
            device._desired_pointing = config_dict.get("sky_coordinates")
            return (ResultCode.OK, "Configure command completed successfully")

    @command(
        dtype_in="DevString",
        doc_in="Configuration parameters encoded in json string",
        dtype_out="DevVarLongStringArray",
        doc_out="[ReturnCode, information-only string]",
    )
    def Configure(self, argin):
        """
        Configure the station_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string
                {
                "station_beam_id":1,
                "station_id": [1,2]
                "channels": [1,2,3,4,5,6,7,8],
                "update_rate": 0.0,
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0]
                }
        :type argin: :py:class:`tango.DevString`

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.command.ResultCode`, str)
        """
        handler = self.get_command_object("Configure")
        (result_code, message) = handler(argin)
        return [[result_code], [message]]


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
