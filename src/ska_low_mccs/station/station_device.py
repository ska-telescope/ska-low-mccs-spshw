#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS station device."""

from __future__ import annotations

import functools
from typing import Any, Optional, cast

import tango
from ska_control_model import CommunicationStatus, HealthState, PowerState, ResultCode
from ska_low_mccs_common import release
from ska_tango_base.commands import SubmittedSlowCommand
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command, device_property

from ska_low_mccs.station.station_component_manager import StationComponentManager
from ska_low_mccs.station.station_health_model import StationHealthModel
from ska_low_mccs.station.station_obs_state_model import StationObsStateModel

DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]

__all__ = ["MccsStation", "main"]


# pylint: disable=too-many-instance-attributes
class MccsStation(SKAObsDevice):
    """An implementation of a station beam Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    StationId = device_property(dtype=int, default_value=0)
    APIUFQDN = device_property(dtype=str)
    TileFQDNs = device_property(dtype=(str,), default_value=[])
    AntennaFQDNs = device_property(dtype=(str,), default_value=[])

    # ---------------
    # Initialisation
    # ---------------
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        # We aren't supposed to define initialisation methods for Tango
        # devices; we are only supposed to define an `init_device` method. But
        # we insist on doing so here, just so that we can define some
        # attributes, thereby stopping the linters from complaining about
        # "attribute-defined-outside-init" etc. We still need to make sure that
        # `init_device` re-initialises any values defined in here.
        super().__init__(*args, **kwargs)

        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: StationHealthModel
        self.component_manager: StationComponentManager
        self._delay_centre: list[float]
        self._obs_state_model: StationObsStateModel
        self._refLatitude: float
        self._refLongitude: float
        self._refHeight: float

    def init_device(self: MccsStation) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsStation) -> None:
        super()._init_state_model()
        self._obs_state_model = StationObsStateModel(
            self.logger, self._update_obs_state
        )
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = StationHealthModel(
            self.APIUFQDN,
            self.AntennaFQDNs,
            self.TileFQDNs,
            self.component_state_changed_callback,
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsStation,
    ) -> StationComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return StationComponentManager(
            self.StationId,
            self.APIUFQDN,
            self.AntennaFQDNs,
            self.TileFQDNs,
            self.logger,
            self._max_workers,
            self._communication_state_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsStation) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("Configure", "configure"),
            ("ApplyPointing", "apply_pointing"),
        ]:
            self.register_command_object(
                command_name,
                SubmittedSlowCommand(
                    command_name,
                    self._command_tracker,
                    self.component_manager,
                    method_name,
                    callback=None,
                    logger=None,
                ),
            )

    # pylint: disable=too-few-public-methods
    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.MccsStation`'s Init command.

        The :py:meth:`~.MccsStation.InitCommand.do` method below is
        called upon :py:class:`~.MccsStation`'s initialisation.
        """

        def do(
            self: MccsStation.InitCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the :py:class:`.MccsStation`.

            :param args: positional args to the component manager method
            :param kwargs: keyword args to the component manager method

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._subarray_id = 0
            self._device._refLatitude = 0.0
            self._device._refLongitude = 0.0
            self._device._refHeight = 0.0
            self._device._beam_fqdns = []
            self._device._transient_buffer_fqdn = ""
            self._device._delay_centre = []
            self._device._calibration_coefficients = []
            self._device._is_calibrated = False
            self._device._calibration_job_id = 0
            self._device._daq_job_id = 0
            self._device._data_directory = ""

            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            self._device.set_change_event("beamFQDNs", True, True)
            self._device.set_archive_event("beamFQDNs", True, True)
            self._device.set_change_event("transientBufferFQDN", True, False)
            self._device.set_archive_event("transientBufferFQDN", True, False)

            super().do()

            return (ResultCode.OK, "Initialisation complete")

    def is_On_allowed(self: MccsStation) -> bool:
        """
        Check if command `Off` is allowed in the current device state.

        :return: ``True`` if the command is allowed
        """
        return self.get_state() in [
            tango.DevState.OFF,
            tango.DevState.STANDBY,
            tango.DevState.ON,
            tango.DevState.UNKNOWN,
            tango.DevState.FAULT,
        ]

    # ----------
    # Callbacks
    # ----------
    def _communication_state_changed(
        self: MccsStation,
        communication_state: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_state: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    def component_state_changed_callback(
        self: MccsStation,
        state_change: dict[str, Any],
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.
        For the power_state parameter it is implemented here to drive the op_state.
        For the health parameter it is implemented to update the health attribute
        and push change events whenever the HealthModel's evaluated health state
        changes.

        :param state_change: a dict containing the state parameters to be set,
            and new values.
        :param fqdn: fully qualified domain name of the device whos state has changed.
            None if the device is a station.

        :raises ValueError: fqdn not found
        """
        if fqdn is None:
            health_state_changed_callback = self.health_changed
            power_state_changed_callback = self._component_power_state_changed
        else:
            device_family = fqdn.split("/")[1]
            if device_family == "apiu":
                health_state_changed_callback = functools.partial(
                    self._health_model.apiu_health_changed, fqdn
                )
                power_state_changed_callback = (
                    self.component_manager._apiu_power_state_changed
                )
            elif device_family == "antenna":
                health_state_changed_callback = functools.partial(
                    self._health_model.antenna_health_changed, fqdn
                )
                power_state_changed_callback = functools.partial(
                    self.component_manager._antenna_power_state_changed, fqdn
                )
            elif device_family == "tile":
                health_state_changed_callback = functools.partial(
                    self._health_model.tile_health_changed, fqdn
                )
                power_state_changed_callback = functools.partial(
                    self.component_manager._tile_power_state_changed, fqdn
                )
            else:
                raise ValueError(
                    f"unknown fqdn '{fqdn}', should be None or belong to antenna,"
                    " tile or apiu"
                )

        if "power_state" in state_change.keys():
            power_state = state_change.get("power_state")
            with self.component_manager.power_state_lock:
                self.component_manager.set_power_state(
                    cast(PowerState, power_state), fqdn=fqdn
                )
                if power_state is not None:
                    power_state_changed_callback(power_state)

        if "health_state" in state_change.keys():
            health = cast(HealthState, state_change.get("health_state"))
            health_state_changed_callback(health)

        if "configuration_changed" in state_change.keys():
            self._obs_state_model.is_configured_changed(True)
            configuration = state_change.get("configuration_changed")
            assert isinstance(configuration, dict)
            self._configure_station(configuration)

    def _component_power_state_changed(
        self: MccsStation,
        power_state: PowerState,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_state: the power mode of the component.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_state])

    def health_changed(self: MccsStation, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state != health:
            self._health_state = health
            self.push_change_event("healthState", health)

    def _configure_station(self: MccsStation, config: dict) -> None:
        """
        Configure the station attributes.

        :param config: the configuration settings for this station.
        """

        def apply_if_valid(attribute_name: str, default: Any) -> Any:
            value = config.get(attribute_name)
            if isinstance(value, type(default)):
                return value
            return default

        self._refLatitude = apply_if_valid("refLatitude", self._refLatitude)
        self._refLongitude = apply_if_valid("refLongitude", self._refLongitude)
        self._refHeight = apply_if_valid("refHeight", self._refHeight)

    # ----------
    # Attributes
    # ----------

    @attribute(
        dtype="float",
        label="refLongitude",
    )
    def refLongitude(self: MccsStation) -> float:
        """
        Return the refLongitude attribute.

        :return: the WGS84 Longitude of the station reference position
        """
        return self._refLongitude

    @attribute(
        dtype="float",
        label="refLatitude",
    )
    def refLatitude(self: MccsStation) -> float:
        """
        Return the refLatitude attribute.

        :return: the WGS84 Latitude of the station reference position
        """
        return self._refLatitude

    @attribute(
        dtype="float",
        label="refHeight",
        unit="meters",
    )
    def refHeight(self: MccsStation) -> float:
        """
        Return the refHeight attribute.

        :return: the ellipsoidal height of the station reference position
        """
        return self._refHeight

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def transientBufferFQDN(self: MccsStation) -> str:
        """
        Return the FQDN of the TANGO device that managers the transient buffer.

        :return: the FQDN of the TANGO device that managers the
            transient buffer
        """
        return self._transient_buffer_fqdn

    @attribute(dtype="DevBoolean")
    def isCalibrated(self: MccsStation) -> bool:
        """
        Return a flag indicating whether this station is currently calibrated or not.

        :return: a flag indicating whether this station is currently
            calibrated or not.
        """
        return self._is_calibrated

    @attribute(dtype="DevBoolean")
    def isConfigured(self: MccsStation) -> bool:
        """
        Return a flag indicating whether this station is currently configured or not.

        :return: a flag indicating whether this station is currently
            configured or not.
        """
        return self.component_manager._is_configured

    @attribute(
        dtype="DevLong",
        format="%i",
    )
    def calibrationJobId(self: MccsStation) -> int:
        """
        Return the calibration job id.

        :return: the calibration job id
        """
        return self._calibration_job_id

    @attribute(
        dtype="DevLong",
        format="%i",
    )
    def daqJobId(self: MccsStation) -> int:
        """
        Return the DAQ job id.

        :return: the DAQ job id
        """
        return self._daq_job_id

    @attribute(
        dtype="DevString",
        format="%s",
    )
    def dataDirectory(self: MccsStation) -> str:
        """
        Return the data directory.

        (the parent directory for all files generated by this station)

        :return: the data directory
        """
        return self._data_directory

    @attribute(
        dtype=("DevString",),
        max_dim_x=8,
        format="%s",
    )
    def beamFQDNs(self: MccsStation) -> list[str]:
        """
        Return the FQDNs of station beams associated with this station.

        :return: the FQDNs of station beams associated with this station
        """
        return self._beam_fqdns

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
    )
    def delayCentre(self: MccsStation) -> list[float]:
        """
        Return the WGS84 position of the delay centre of the station.

        :todo: WGS84 is a datum. What is the coordinate system?
            Latitude and longitude? Or is it SUTM50 eastings and
            northings? Either way, do we need to allow for elevation
            too?

        :return: the WGS84 position of the delay centre of the station
        """
        return self._delay_centre

    @delayCentre.write  # type: ignore[no-redef]
    def delayCentre(self: MccsStation, value: list[float]) -> None:
        """
        Set the delay centre of the station.

        :param value: WGS84 position
        """
        self._delay_centre = value

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=512,
    )
    def calibrationCoefficients(self: MccsStation) -> list[float]:
        """
        Return the calibration coefficients for the station.

        :todo: How big should this array be? Gain and offset per antenna
            per channel. This station can have up to 16 tiles of up to
            16 antennas, so that is 2 x 16 x 16 = 512 coefficients per
            channel. But how many channels?

        :return: the calibration coefficients
        """
        return self._calibration_coefficients

    # --------
    # Commands
    # --------

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def Configure(self: MccsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the station with all relevant parameters.

        Also configures children device that are connected to the station.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:
            >>> dp = tango.DeviceProxy("mccs/station/001")
            >>> dp.command_inout("Configure", json_str)
        """
        handler = self.get_command_object("Configure")
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    def ApplyPointing(
        self: MccsStation, argin: list[float]
    ) -> DevVarLongStringArrayType:
        """
        Set the pointing delay parameters of this Station's Tiles.

        :param argin: an array containing a beam index followed by antenna delays

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.

        :example:

        >>> dp = tango.DeviceProxy("mccs/station/01")
        >>> dp.command_inout("ApplyPointing", delay_list)
        """
        handler = self.get_command_object("ApplyPointing")
        (return_code, message) = handler(argin)
        return ([return_code], [message])


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:  # pragma: no cover
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsStation.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
