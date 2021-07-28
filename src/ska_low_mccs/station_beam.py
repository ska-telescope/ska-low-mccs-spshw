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

from __future__ import annotations  # allow forward references in type hints

__all__ = ["MccsStationBeam", "main"]

import json
import logging
import threading
from typing import List, Optional, Tuple

from tango import EnsureOmniThread
from tango.server import attribute, command
from tango.server import device_property

from ska_tango_base import SKABaseDevice, SKAObsDevice, DeviceStateModel
from ska_tango_base.control_model import HealthState
from ska_tango_base.commands import ResponseCommand, ResultCode
import ska_low_mccs.release as release

from ska_low_mccs.hardware import (
    ConnectionStatus,
    HardwareDriver,
    HardwareFactory,
    HardwareHealthEvaluator,
    HardwareManager,
)
from ska_low_mccs.health import MutableHealthModel
from ska_low_mccs import MccsDeviceProxy

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class StationBeamHealthEvaluator(HardwareHealthEvaluator):
    """
    A :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareHealthEval uator` for a
    station beam. A station beam doesn't have hardware as such. Here we are pretending
    it does because we have to set health to DEGRADED if the beam is not locked, so for
    now we pretend that the `isBeamLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def evaluate_health(
        self: StationBeamHealthEvaluator, hardware: HardwareDriver
    ) -> HealthState:
        """
        Evaluate the health of the "hardware".

        :param hardware: the "hardware" for which health is being
            evaluated

        :return: the evaluated health of the hardware
        """
        if not hardware.is_locked:
            return HealthState.DEGRADED
        return HealthState.OK


class StationBeamDriver(HardwareDriver):
    """
    A hardware driver for a station beam. A station beam doesn't actually have hardware.
    Here we are shoe-horning the station beam implementation into the hardware model by
    pretending that the `isBeamLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self: StationBeamDriver, is_locked: bool = False) -> None:
        """
        Create a new driver for station beam hardware.

        :param is_locked: initial value for whether this beam is locked
        """
        super().__init__(True)
        self._is_locked = is_locked

    @property
    def connection_status(self: StationBeamDriver) -> ConnectionStatus:
        """
        Returns the status of the driver-hardware connection.

        :return: the status of the driver-hardware connection.
        """
        return ConnectionStatus.CONNECTED

    @property
    def is_locked(self: StationBeamDriver) -> bool:
        """
        Whether the station beam is locked.

        :return: whether the station beam is locked
        """
        return self._is_locked

    @is_locked.setter
    def is_locked(self: StationBeamDriver, value: bool) -> None:
        """
        Setter for the is_locked property.

        :param value: whether the station beam is locked
        """
        self._is_locked = value


class StationBeamHardwareFactory(HardwareFactory):
    """
    A hardware factory for a station beam. A station beam doesn't actually have
    hardware. Here we are shoe-horning the station beam implementation into the hardware
    model by pretending that the `isLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self: StationBeamHardwareFactory, is_locked: bool) -> None:
        """
        Create a new factory instance.

        :param is_locked: initial value for whether this beam is locked
        """
        self._hardware = StationBeamDriver(is_locked=is_locked)

    @property
    def hardware(self: StationBeamHardwareFactory) -> StationBeamDriver:
        """
        Return a station beam driver created by this factory.

        :return: an station beam driver created by this factory
        """
        return self._hardware


class StationBeamHardwareManager(HardwareManager):
    """
    This class manages station beam "hardware".  A station beam doesn't actually have
    hardware. Here we are shoe-horning the station beam implementation into the hardware
    model by pretending that the `isLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(
        self: StationBeamHardwareManager,
        is_locked: bool = False,
        _factory: Optional[StationBeamHardwareFactory] = None,
    ) -> None:
        """
        Initialise a new StationBeamHardwareManager instance.

        :param is_locked: initial value for whether this beam is locked
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        """
        hardware_factory = _factory or StationBeamHardwareFactory(is_locked)
        super().__init__(hardware_factory, StationBeamHealthEvaluator())

    @property
    def is_locked(self: StationBeamHardwareManager) -> bool:
        """
        Whether the station beam is locked.

        :return: whether the station beam is locked
        """
        return self._factory.hardware.is_locked

    @is_locked.setter
    def is_locked(self: StationBeamHardwareManager, value: bool) -> None:
        """
        Setter for the is_locked property.

        :param value: whether the station beam is locked
        """
        self._factory.hardware.is_locked = value
        self._update_health()


class MccsStationBeam(SKAObsDevice):
    """
    Prototype TANGO device server for the MCCS Station Beam.

    This class is a subclass of :py:class:`ska_tango_base.SKAObsDevice`.

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

        The :py:meth:`~.MccsStationBeam.InitCommand.do` method below is called upon
        :py:class:`~.MccsStationBeam`'s initialisation.
        """

        def __init__(
            self: MccsStationBeam.InitCommand,
            target: object,
            state_model: DeviceStateModel,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Create a new InitCommand.

            :param target: the object that this command acts upon; for
                example, the device for which this class implements the
                command
            :param state_model: the state model that this command uses
                 to check that it is allowed to run, and that it drives
                 with actions.
            :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
            """
            super().__init__(target, state_model, logger)

            self._thread: Optional[threading.Thread] = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self: MccsStationBeam.InitCommand) -> tuple[ResultCode, str]:
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
            """
            (result_code, message) = super().do()

            device = self.target
            device._beam_id = device.BeamId
            # Changed station_id to list.
            # This is a divergance from the ICD
            device._station_ids = []
            device._station_fqdn = ""
            device._logical_beam_id = 0
            device._channels = []
            device._desired_pointing = []
            device._pointing_delay = []
            device._pointing_delay_rate = []
            device._update_rate = 0.0
            device._antenna_weights = []
            device._phase_centre = []

            device._build_state = release.get_release_info()
            device._version_id = release.version

            self._thread = threading.Thread(
                target=self._initialise_connections, args=(device,)
            )
            with self._lock:
                self._thread.start()
                return (ResultCode.STARTED, "Init command started")

        def _initialise_connections(
            self: MccsStationBeam.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Thread target for asynchronous initialisation of connections to external
            entities such as hardware and other devices.

            :param device: the device being initialised
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

        def _initialise_hardware_management(
            self: MccsStationBeam.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Initialise the connection to the hardware being managed by this device. May
            also register commands that depend upon a connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            """
            device.hardware_manager = StationBeamHardwareManager()

        def _initialise_health_monitoring(
            self: MccsStationBeam.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            """
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = MutableHealthModel(
                device.hardware_manager,
                None,
                self.logger,
                device.health_changed,
            )

        def interrupt(self: MccsStationBeam.InitCommand) -> bool:
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

    def init_command_objects(self: MccsStationBeam) -> None:
        """Initialises the command handlers for commands supported by this device."""
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("ApplyPointing", self.ApplyPointingCommand(*args))

    def always_executed_hook(self: MccsStationBeam) -> None:
        """Method always executed before any TANGO command is executed."""
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self: MccsStationBeam) -> None:
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
        pass

    # ----------
    # Attributes
    # ----------
    def health_changed(self: MccsStationBeam, health: HealthState) -> None:
        """
        Callback to be called whenever the HealthModel's health state changes;
        responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        """
        self._health_state: HealthState  # typehints only
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevLong", format="%i")
    def beamId(self: MccsStationBeam) -> int:
        """
        Return the beam id.

        :return: the beam id
        """
        return self._beam_id

    @attribute(dtype=("DevLong",), max_dim_x=512, format="%i")
    def stationIds(self: MccsStationBeam) -> list[int]:
        """
        Return the station ids.

        :return: the station ids
        """
        return self._station_ids

    @stationIds.write  # type: ignore[no-redef]
    def stationIds(self: MccsStationBeam, station_ids: list[int]) -> None:
        """
        Set the station ids.

        :param station_ids: ids of the stations for this beam
        """
        self._station_ids = station_ids

    @attribute(dtype="DevString", max_dim_x=512, format="%s")
    def stationFqdn(self: MccsStationBeam) -> str:
        """
        Return the station FQDN.

        :return: the station FQDN
        """
        return self._station_fqdn

    @stationFqdn.write  # type: ignore[no-redef]
    def stationFqdn(self: MccsStationBeam, station_fqdn: str) -> None:
        """
        Set the station fqdn.

        :param station_fqdn: fqdn of the station this beam is assigned to
        """
        if self._station_fqdn:
            self.health_model.remove_devices((self._station_fqdn,))
        if station_fqdn:
            self.health_model.add_devices((station_fqdn,))
        self._station_fqdn = station_fqdn

    @attribute(dtype="DevLong", format="%i", max_value=7, min_value=0)
    def logicalBeamId(self: MccsStationBeam) -> int:
        """
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        """
        return self._logical_beam_id

    @logicalBeamId.write  # type: ignore[no-redef]
    def logicalBeamId(self: MccsStationBeam, logical_beam_id: int) -> None:
        """
        Set the logical beam id.

        :param logical_beam_id: the logical beam id
        """
        self._logical_beam_id = logical_beam_id

    @attribute(
        dtype="DevDouble", unit="Hz", standard_unit="s^-1", max_value=1e37, min_value=0
    )
    def updateRate(self: MccsStationBeam) -> float:
        """
        Return the update rate (in hertz) for this station beam.

        :return: the update rate for this station beam
        """
        return self._update_rate

    @attribute(dtype="DevBoolean")
    def isBeamLocked(self: MccsStationBeam) -> bool:
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        """
        return self.hardware_manager.is_locked

    @isBeamLocked.write  # type: ignore[no-redef]
    def isBeamLocked(self: MccsStationBeam, value: bool) -> None:
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        """
        self.hardware_manager.is_locked = value

    @attribute(dtype=(("DevLong",),), max_dim_y=384, max_dim_x=4)
    def channels(self: MccsStationBeam) -> list[list[int]]:
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        """
        return self._channels

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def desiredPointing(self: MccsStationBeam) -> list[float]:
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam conforming to the Sky Coordinate Set
            definition
        """
        return self._desired_pointing

    @desiredPointing.write  # type: ignore[no-redef]
    def desiredPointing(self: MccsStationBeam, values: list[float]) -> None:
        """
        Set the desired pointing of this beam.

        * activation time (s) -- value range 0-10^37
        * azimuth position (deg) -- value range 0-360
        * azimuth speed (deg/s) -- value range 0-10^37
        * elevation position (deg) -- value range 0-90
        * elevation rate (deg/s) -- value range 0-10^37

        :param values: the desired pointing of this beam, expressed as a
            sky coordinate set
        """
        self._desired_pointing = values

    @attribute(dtype=("DevDouble",), max_dim_x=256)
    def pointingDelay(self: MccsStationBeam) -> list[float]:
        """
        Return the pointing delay per antenna.

        :return: the pointing delay per antenna
        """
        return self._pointing_delay

    @pointingDelay.write  # type: ignore[no-redef]
    def pointingDelay(self: MccsStationBeam, values: list[float]) -> None:
        """
        Set the pointing delay per antenna.

        :param values: the desired pointing delay per antenna
        """
        self._pointing_delay = values

    @attribute(dtype=("DevDouble",), max_dim_x=256)
    def pointingDelayRate(self: MccsStationBeam) -> list[float]:
        """
        Return the pointing delay rate for each antenna.

        :return: the pointing delay rate per antenna
        """
        return self._pointing_delay_rate

    @pointingDelayRate.write  # type: ignore[no-redef]
    def pointingDelayRate(self: MccsStationBeam, values: list[float]):
        """
        Set the pointing delay rate for each antenna.

        :param values: the desired pointing delay rate per antenna
        """
        self._pointing_delay_rate = values

    @attribute(dtype=("DevDouble",), max_dim_x=256)
    def antennaWeights(self: MccsStationBeam) -> list[float]:
        """
        Return the antenna weights.

        :return: the antenna weights
        """
        return self._antenna_weights

    @antennaWeights.write  # type: ignore[no-redef]
    def antennaWeights(self: MccsStationBeam, value: list[float]) -> None:
        """
        Set the antenna weights.

        :param value: the new antenna weights
        """
        self._antenna_weights = value

    # --------
    # Commands
    # --------
    class ConfigureCommand(ResponseCommand):
        """Class for handling the Configure(argin) command."""

        SUCCEEDED_MESSAGE = "Configure command completed OK"

        def do(self: MccsStationBeam, argin: str) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for the
            :py:meth:`.MccsStationBeam.Configure` command

            :param argin: Configuration specification dict as a json
                string

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            config_dict = json.loads(argin)
            device = self.target
            device._station_ids = config_dict.get("station_ids", [])
            device._channels = config_dict.get("channels", [])
            device._update_rate = config_dict.get("update_rate")
            device._desired_pointing = config_dict.get("sky_coordinates", [])
            device._antenna_weights = config_dict.get("antenna_weights", [])
            device._phase_centre = config_dict.get("phase_centre", [])
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(self: MccsStationBeam, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the station_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string
                {
                "subarray_beam_id":1,
                "station_ids": [1,2]
                "channels": [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                "update_rate": 0.0,
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0]
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0]
                }

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Configure")
        (result_code, status) = handler(argin)
        return ([result_code], [status])

    class ApplyPointingCommand(ResponseCommand):
        """Class for handling the ApplyPointing(argin) command."""

        SUCCEEDED_MESSAGE = "ApplyPointing command completed OK"
        FAILED_MESSAGE = "ApplyPointing command failed"

        def do(self: MccsStationBeam) -> tuple[ResultCode, str]:
            """
            Stateless do-hook for the
            :py:meth:`.MccsStationBeam.ApplyPointing` command

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            device = self.target
            # zip delays and rates for SetPointingDelay
            zipped_delays_and_rates = [
                item
                for pair in zip(
                    device._pointing_delay, device._pointing_delay_rate + [0]
                )
                for item in pair
            ]
            station_pointing_args = [device._logical_beam_id] + zipped_delays_and_rates
            station_proxy = MccsDeviceProxy(device._station_fqdn, self.logger)
            (result_code, message) = station_proxy.ApplyPointing(station_pointing_args)
            if result_code == ResultCode.FAILED:
                return (result_code, self.FAILED_MESSAGE)
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_out="DevVarLongStringArray")
    def ApplyPointing(self: MccsStationBeam) -> DevVarLongStringArrayType:
        """
        Apply pointing delays to antennas associated with the station_beam.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ApplyPointing")
        (result_code, message) = handler()
        return ([result_code], [message])


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsStationBeam.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
