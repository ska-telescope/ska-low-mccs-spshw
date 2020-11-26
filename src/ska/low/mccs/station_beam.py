# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MCCS Station Beam TANGO device prototype.

Prototype TANGO device server for the MCSS Station Beam
"""
__all__ = ["MccsStationBeam", "main"]

import json
import threading

from tango import EnsureOmniThread
from tango.server import attribute, command
from tango.server import device_property

from ska.base import SKAObsDevice
from ska.base.control_model import HealthState
from ska.base.commands import ResponseCommand, ResultCode
import ska.low.mccs.release as release

from ska.low.mccs.events import EventManager
from ska.low.mccs.hardware import (
    HardwareDriver,
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareManager,
)
from ska.low.mccs.health import HealthModel


class StationBeamHealthEvaluator(HardwareHealthEvaluator):
    """
    A :py:class:`~ska.low.mccs.hardware.HardwareHealthEvaluator` for a
    station beam. A station beam doesn't have hardware as such. Here we
    are pretending it does because we have to set health to DEGRADED if
    the beam is not locked, so for now we pretend that the
    `isBeamLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def evaluate_health(self, hardware):
        """
        Evaluate the health of the "hardware".

        :param hardware: the "hardware" for which health is being
            evaluated
        :type hardware:
            :py:class:`~ska.low.mccs.hardware.HardwareDriver`

        :return: the evaluated health of the hardware
        :rtype: :py:class:`~ska.base.control_model.HealthState`
        """
        if not hardware.is_locked:
            return HealthState.DEGRADED
        return HealthState.OK


class StationBeamDriver(HardwareDriver):
    """
    A hardware driver for a station beam. A station beam doesn't
    actually have hardware. Here we are shoe-horning the station beam
    implementation into the hardware model by pretending that the
    `isBeamLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self, is_locked=False):
        """
        Create a new driver for station beam hardware.

        :param is_locked: initial value for whether this beam is locked
        :type is_locked: bool
        """
        self._is_locked = is_locked

    @property
    def is_connected(self):
        """
        Whether this station beam "hardware" driver has a connection to
        the hardware.

        :return: whether this antenna hardware driver has a connection
            to the hardware; hardwired to return True
        :rtype: bool
        """
        return True

    @property
    def is_locked(self):
        """
        Whether the station beam is locked.

        :return: whether the station beam is locked
        :rtype: bool
        """
        return self._is_locked

    @is_locked.setter
    def is_locked(self, value):
        """
        Setter for the is_locked property.

        :param value: whether the station beam is locked
        :type value: bool
        """
        self._is_locked = value


class StationBeamHardwareFactory(HardwareFactory):
    """
    A hardware factory for a station beam. A station beam doesn't
    actually have hardware. Here we are shoe-horning the station beam
    implementation into the hardware model by pretending that the
    `isLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self, is_locked):
        """
        Create a new factory instance.

        :param is_locked: initial value for whether this beam is locked
        :type is_locked: bool
        """
        self._hardware = StationBeamDriver(is_locked=is_locked)

    @property
    def hardware(self):
        """
        Return a station beam driver created by this factory.

        :return: an station beam driver created by this factory
        :rtype: :py:class:`StationBeamDriver`
        """
        return self._hardware


class StationBeamHardwareManager(HardwareManager):
    """
    This class manages station beam "hardware".  A station beam doesn't
    actually have hardware. Here we are shoe-horning the station beam
    implementation into the hardware model by pretending that the
    `isLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self, is_locked=False, _factory=None):
        """
        Initialise a new TileHardwareManager instance.

        :param is_locked: initial value for whether this beam is locked
        :type is_locked: bool
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        :type _factory: :py:class:`StationBeamHardwareFactory`
        """
        hardware_factory = _factory or StationBeamHardwareFactory(is_locked)
        super().__init__(hardware_factory, StationBeamHealthEvaluator())

    @property
    def is_locked(self):
        """
        Whether the station beam is locked.

        :return: whether the station beam is locked
        :rtype: bool
        """
        return self._factory.hardware.is_locked

    @is_locked.setter
    def is_locked(self, value):
        """
        Setter for the is_locked property.

        :param value: whether the station beam is locked
        :type value: bool
        """
        self._factory.hardware.is_locked = value
        self._update_health()


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
        A class for :py:class:`~.MccsStationBeam`'s Init command.

        The :py:meth:`~.MccsStationBeam.InitCommand.do` method below is
        called upon :py:class:`~.MccsStationBeam`'s initialisation.
        """

        def __init__(self, target, state_model, logger=None):
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :type target: object
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :type state_model:
                :py:class:`~ska.base.DeviceStateModel`
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            :type logger: :py:class:`logging.Logger`
            """
            super().__init__(target, state_model, logger)

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self):
            """
            Initialises the attributes and properties of the
            :py:class:`.MccsStationBeam`.

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

            device._build_state = release.get_release_info()
            device._version_id = release.version

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(self, device):
            """
            Thread target for asynchronous initialisation of connections
            to external entities such as hardware and other devices.

            :param device: the device being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            # https://pytango.readthedocs.io/en/stable/howto.html
            # #using-clients-with-multithreading
            with EnsureOmniThread():
                self._initialise_hardware_management(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                self._initialise_health_monitoring(device)
                if self._interrupt:
                    self._thread = None
                    self._interrupt = False
                    return
                with self._lock:
                    self.succeeded()
                    self._thread = None
                    self._interrupt = False

        def _initialise_hardware_management(self, device):
            """
            Initialise the connection to the hardware being managed by
            this device. May also register commands that depend upon a
            connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.hardware_manager = StationBeamHardwareManager()

        def _initialise_health_monitoring(self, device):
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            :type device: :py:class:`~ska.base.SKABaseDevice`
            """
            device.event_manager = EventManager(self.logger)

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager,
                None,
                device.event_manager,
                device.health_changed,
            )

        def interrupt(self):
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

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
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsStationBeam.InitCommand.do` method of
        the nested :py:class:`~.MccsStationBeam.InitCommand`
        class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsStationBeam.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska.base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevLong", format="%i", polling_period=1000, doc="ID of the beam")
    def beamId(self):
        """
        Return the beam id.

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
        Return the station ids.

        :return: the station ids
        :rtype: List[int]
        """
        return self._station_ids

    @stationIds.write
    def stationIds(self, station_ids):
        """
        Set the station ids.

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
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        :rtype: int
        """
        return self._logical_beam_id

    @logicalBeamId.write
    def logicalBeamId(self, logical_beam_id):
        """
        Set the logical beam id.

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
        Return the update rate (in hertz) for this station beam.

        :return: the update rate for this station beam
        :rtype: float
        """
        return self._update_rate

    @attribute(
        dtype="DevBoolean",
        doc="Flag specifying whether beam is locked to target",
        polling_period=1000,
    )
    def isBeamLocked(self):
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        :rtype: bool
        """
        return self.hardware_manager.is_locked

    @isBeamLocked.write
    def isBeamLocked(self, value):
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        :type value: bool
        """
        self.hardware_manager.is_locked = value

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
        :rtype: list(int)
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
        :rtype: list(float) conforming to the Sky Coordinate Set
            definition
        """
        return self._desired_pointing

    @desiredPointing.write
    def desiredPointing(self, values):
        """
        Set the desired pointing of this beam.

        * activation time (s) -- value range 0-10^37
        * azimuth position (deg) -- value range 0-360
        * azimuth speed (deg/s) -- value range 0-10^37
        * elevation position (deg) -- value range 0-90
        * elevation rate (deg/s) -- value range 0-10^37

        :param values: the desired pointing of this beam, expressed as a
            sky coordinate set
        :type values: list(float)
        """
        self._desired_pointing = values

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Latest computed pointing delay per antenna",
    )
    def pointingDelay(self):
        """
        Return the pointing delay per antenna.

        :return: the pointing delay per antenna
        :rtype: list(float)
        """
        return self._pointing_delay

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=256,
        doc="Latest computed pointing delay rate per antenna",
    )
    def pointingDelayRate(self):
        """
        Return the pointing delay rate for each antenna.

        :return: the pointing delay rate per antenna
        :rtype: list(float)
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
        Return the antenna weights.

        :return: the antenna weights
        :rtype: list(float)
        """
        return self._antenna_weights

    @antennaWeights.write
    def antennaWeights(self, value):
        """
        Set the antenna weights.

        :param value: the new antenna weights
        :type value: list(float)
        """
        self._antenna_weights = value

    # --------
    # Commands
    # --------
    class ConfigureCommand(ResponseCommand):
        """
        Class for handling the Configure(argin) command.
        """

        def do(self, argin):
            """
            Stateless do-hook for the
            :py:meth:`.MccsStationBeam.Configure` command

            :param argin: Configuration specification dict as a json
                string
            :type argin: str

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
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
        :type argin: str

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        :rtype: (:py:class:`ska.base.commands.ResultCode`, str)
        """
        handler = self.get_command_object("Configure")
        (result_code, message) = handler(argin)
        return [[result_code], [message]]


# ----------
# Run server
# ----------
def main(args=None, **kwargs):
    """
    Entry point for module.

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
