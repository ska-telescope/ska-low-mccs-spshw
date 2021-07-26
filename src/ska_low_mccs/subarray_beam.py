# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MCCS Subarray Beam TANGO device prototype.

Prototype TANGO device server for the MCSS Subarray Beam
"""
from __future__ import annotations  # allow forward references in type hints

__all__ = [
    "MccsSubarrayBeam",
    "SubarrayBeamHealthEvaluator",
    "SubarrayBeamDriver",
    "SubarrayBeamHardwareFactory",
    "SubarrayBeamHardwareManager",
    "main",
]

import json
import logging
import threading
from typing import List, Tuple

from tango import EnsureOmniThread
from tango.server import attribute, command

from ska_tango_base import SKAObsDevice, SKABaseDevice
from ska_tango_base.base_device import DeviceStateModel
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
from ska_low_mccs.health import HealthModel


class SubarrayBeamHealthEvaluator(HardwareHealthEvaluator):
    """
    A
    :py:class:`~ska_low_mccs.hardware.base_hardware.HardwareHealthEvaluator`
    for a subarray beam.

    A Subarray beam doesn't have hardware as such. Here we are
    pretending it does because we have to set health to DEGRADED if the
    beam is not locked, so for now we pretend that the `isBeamLocked`
    attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def evaluate_health(
        self: SubarrayBeamHealthEvaluator, hardware: HardwareDriver
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


class SubarrayBeamDriver(HardwareDriver):
    """
    A hardware driver for a subarray beam. A subarray beam doesn't actually have
    hardware. Here we are shoe-horning the subarray beam implementation into the
    hardware model by pretending that the `isBeamLocked` attribute of the associated
    stations is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self: SubarrayBeamDriver, is_locked: bool = False) -> None:
        """
        Create a new driver for subarray beam hardware.

        :param is_locked: initial value for whether this beam is locked
        """
        super().__init__(True)
        self._is_locked = is_locked

    @property
    def connection_status(self: SubarrayBeamDriver) -> ConnectionStatus:
        """
        Returns the status of the driver-hardware connection.

        :return: the status of the driver-hardware connection.
        """
        return ConnectionStatus.CONNECTED

    @property
    def is_locked(self: SubarrayBeamDriver) -> bool:
        """
        Whether the subarray beam is locked.

        :return: whether the subarray beam is locked
        """
        return self._is_locked

    @is_locked.setter
    def is_locked(self: SubarrayBeamDriver, value: bool) -> None:
        """
        Setter for the is_locked property.

        :param value: whether the subarray beam is locked
        """
        self._is_locked = value


class SubarrayBeamHardwareFactory(HardwareFactory):
    """
    A hardware factory for a subarray beam. A subarray beam doesn't actually have
    hardware. Here we are shoe-horning the subarray beam implementation into the
    hardware model by pretending that the `isLocked` attribute is a hardware property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(self: SubarrayBeamHardwareFactory, is_locked: bool) -> None:
        """
        Create a new factory instance.

        :param is_locked: initial value for whether this beam is locked
        """
        self._hardware = SubarrayBeamDriver(is_locked=is_locked)

    @property
    def hardware(self: SubarrayBeamHardwareFactory) -> SubarrayBeamDriver:
        """
        Return a subarray beam driver created by this factory.

        :return: an subarray beam driver created by this factory
        """
        return self._hardware


class SubarrayBeamHardwareManager(HardwareManager):
    """
    This class manages subarray beam "hardware".

    A subarray beam doesn't actually have hardware. Here we are
    shoe-horning the subarray beam implementation into the hardware
    model by pretending that the `isLocked` attribute is a hardware
    property.

    :todo: It seems that the health of a device can depend on more than
        just hardware health plus subservient device health. Here,
        health depends on whether the beam is locked, which appears to
        be a property of neither the hardware nor subservient devices.
        The health model may need to be reviewed in light of this.
    """

    def __init__(
        self: SubarrayBeamHardwareManager,
        is_locked: bool = True,
        _factory: SubarrayBeamHardwareFactory = None,
    ) -> None:
        """
        Initialise a new SubarrayBeamHardwareManager instance.

        :param is_locked: initial value for whether this beam is locked
        :param _factory: allows for substitution of a hardware factory.
            This is useful for testing, but generally should not be used
            in operations.
        """
        hardware_factory = _factory or SubarrayBeamHardwareFactory(is_locked)
        super().__init__(hardware_factory, SubarrayBeamHealthEvaluator())

    @property
    def is_locked(self: SubarrayBeamHardwareManager) -> bool:
        """
        Whether the subarray beam is locked.

        :return: whether the subarray beam is locked
        """
        return self._factory.hardware.is_locked

    @is_locked.setter
    def is_locked(self: SubarrayBeamHardwareManager, value: bool) -> None:
        """
        Setter for the is_locked property.

        :param value: whether the subarray beam is locked
        """
        self._factory.hardware.is_locked = value
        self._update_health()


class MccsSubarrayBeam(SKAObsDevice):
    """
    Prototype TANGO device server for the MCCS Subarray Beam.

    This class is a subclass of :py:class:`ska_tango_base.SKAObsDevice`.

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------
    # SubarrayBeamId = device_property(dtype=int, default_value=0)
    # BeamId = device_property(dtype=int, default_value=0)

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.MccsSubarrayBeam`'s Init command.

        The :py:meth:`~.MccsSubarrayBeam.InitCommand.do` method below is
        called upon :py:class:`~.MccsSubarrayBeam`'s initialisation.
        """

        def __init__(
            self: MccsSubarrayBeam.InitCommand,
            target: object,
            state_model: DeviceStateModel,
            logger: logging.Logger = None,
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

            self._thread = None
            self._lock = threading.Lock()
            self._interrupt = False

        def do(self: MccsSubarrayBeam.InitCommand) -> Tuple[ResultCode, str]:
            """
            Initialises the attributes and properties of the
            :py:class:`.MccsSubarrayBeam`.

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
            device._logical_beam_id = 0
            # Changed station_id to list.
            # This is a divergance from the ICD
            device._subarray_id = 0
            device._subarray_beam_id = 0
            device._station_ids = []
            device._channels = []
            device._desired_pointing = []
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
            self: MccsSubarrayBeam.InitCommand, device: SKABaseDevice
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
            self: MccsSubarrayBeam.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Initialise the connection to the hardware being managed by this device. May
            also register commands that depend upon a connection to that hardware.

            :param device: the device for which a connection to the
                hardware is being initialised
            """
            device.hardware_manager = SubarrayBeamHardwareManager()

        def _initialise_health_monitoring(
            self: MccsSubarrayBeam.InitCommand, device: SKABaseDevice
        ) -> None:
            """
            Initialise the health model for this device.

            :param device: the device for which the health model is
                being initialised
            """
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                device.hardware_manager, None, self.logger, device.health_changed
            )

        def interrupt(self: MccsSubarrayBeam.InitCommand) -> bool:
            """
            Interrupt the initialisation thread (if one is running)

            :return: whether the initialisation thread was interrupted
            :rtype: bool
            """
            if self._thread is None:
                return False
            self._interrupt = True
            return True

    def init_command_objects(self: MccsSubarrayBeam) -> None:
        """Initialises the command handlers for commands supported by this device."""
        super().init_command_objects()

        args = (self, self.state_model, self.logger)
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("Scan", self.ScanCommand(*args))

    def always_executed_hook(self: MccsSubarrayBeam) -> None:
        """Method always executed before any TANGO command is executed."""
        if self.hardware_manager is not None:
            self.hardware_manager.poll()

    def delete_device(self: MccsSubarrayBeam) -> None:
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsSubarrayBeam.InitCommand.do` method of
        the nested :py:class:`~.MccsSubarrayBeam.InitCommand`
        class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsSubarrayBeam.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        pass

    # ----------
    # Attributes
    # ----------
    def health_changed(self: MccsSubarrayBeam, health: HealthState) -> None:
        """
        Callback to be called whenever the HealthModel's health state changes;
        responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevLong", format="%i")
    def subarrayId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self._subarray_id

    @attribute(dtype="DevLong", format="%i", max_value=47, min_value=0)
    def subarrayBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray beam id.

        :return: the subarray beam id
        """
        return self._subarray_beam_id

    @attribute(dtype=("DevLong",), max_dim_x=512, format="%i")
    def stationIds(self: MccsSubarrayBeam) -> List[int]:
        """
        Return the station ids.

        :return: the station ids
        """
        return self._station_ids

    @stationIds.write
    def stationIds(self: MccsSubarrayBeam, station_ids: List[int]) -> None:
        """
        Set the station ids.

        :param station_ids: ids of the stations for this beam
        """
        self._station_ids = station_ids

    @attribute(dtype="DevLong", format="%i", max_value=7, min_value=0)
    def logicalBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        """
        return self._logical_beam_id

    @logicalBeamId.write
    def logicalBeamId(self: MccsSubarrayBeam, logical_beam_id: int) -> None:
        """
        Set the logical beam id.

        :param logical_beam_id: the logical beam id
        """
        self._logical_beam_id = logical_beam_id

    @attribute(
        dtype="DevDouble", unit="Hz", standard_unit="s^-1", max_value=1e37, min_value=0
    )
    def updateRate(self: MccsSubarrayBeam) -> float:
        """
        Return the update rate (in hertz) for this subarray beam.

        :return: the update rate for this subarray beam
        """
        return self._update_rate

    @attribute(dtype="DevBoolean")
    def isBeamLocked(self: MccsSubarrayBeam) -> bool:
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        """
        return self.hardware_manager.is_locked

    @isBeamLocked.write
    def isBeamLocked(self: MccsSubarrayBeam, value: bool) -> None:
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        :type value: bool
        """
        self.hardware_manager.is_locked = value

    @attribute(dtype=(("DevLong",),), max_dim_y=384, max_dim_x=4)
    def channels(self: MccsSubarrayBeam) -> List[list[int]]:
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        """
        return self._channels

    @attribute(dtype=("DevFloat",), max_dim_x=384)
    def antennaWeights(self: MccsSubarrayBeam) -> List[float]:
        """
        Return the antenna weights configured for this beam.

        :return: antenna weightd
        """
        return self._antenna_weights

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def desiredPointing(self: MccsSubarrayBeam) -> list(float):
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam, conforming to the Sky Coordinate Set definition
        """
        return self._desired_pointing

    @desiredPointing.write
    def desiredPointing(self: MccsSubarrayBeam, values: List[float]) -> None:
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

    # --------
    # Commands
    # --------
    class ConfigureCommand(ResponseCommand):
        """Class for handling the Configure(argin) command."""

        SUCCEEDED_MESSAGE = "Configure command completed OK"

        def do(
            self: MccsSubarrayBeam.ConfigureCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for the
            :py:meth:`.MccsSubarrayBeam.Configure` command

            :param argin: Configuration specification dict as a json
                string
                {
                "subarray_beam_id": 1,
                "station_ids": [1,2],
                "update_rate": 0.0,
                "channels": [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0],
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            config_dict = json.loads(argin)
            device = self.target
            device._logical_beam_id = 0
            device._subarray_beam_id = config_dict.get("subarray_beam_id")
            device._station_ids = config_dict.get("station_ids", [])
            device._channels = config_dict.get("channels", [])
            device._update_rate = config_dict.get("update_rate")
            device._desired_pointing = config_dict.get("sky_coordinates", [])
            device._antenna_weights = config_dict.get("antenna_weights", [])
            device._phase_centre = config_dict.get("phase_centre", [])

            # TODO: Forward configuration settings to all the subservient Stations
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(self: MccsSubarrayBeam, argin: str) -> Tuple[ResultCode, str]:
        """
        Configure the subarray_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Configure")
        (result_code, status) = handler(argin)
        return [[result_code], [status]]

    class ScanCommand(ResponseCommand):
        """Class for handling the Scan(argin) command."""

        SUCCEEDED_MESSAGE = "Scan command completed OK"

        def do(
            self: MccsSubarrayBeam.ScanCommand, argin: str
        ) -> Tuple[ResultCode, str]:
            """
            Stateless do-hook for the
            :py:meth:`.MccsSubarrayBeam.Scan` command

            :param argin: Scan parameters encoded in a json string
                {
                "scan_id": 1,
                "scan_time": 4
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            kwargs = json.loads(argin)
            device = self.target
            device._scan_id = kwargs.get("scan_id")
            device._scan_time = kwargs.get("scan_time")

            # TODO: Forward scan command and parameters to all the subservient Stations
            return (ResultCode.OK, self.SUCCEEDED_MESSAGE)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Scan(self: MccsSubarrayBeam, argin: str) -> Tuple[ResultCode, str]:
        """
        Start a scan on the subarray_beam.

        :param argin: Scan parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Scan")
        (result_code, status) = handler(argin)
        return [[result_code], [status]]


# ----------
# Run server
# ----------
def main(args: str = None, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsSubarrayBeam.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
