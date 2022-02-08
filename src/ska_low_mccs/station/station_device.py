# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS station device."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

import tango
from ska_tango_base.commands import ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, PowerMode
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command, device_property

import ska_low_mccs.release as release
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.station import StationComponentManager, StationHealthModel, StationObsStateModel

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]

__all__ = ["MccsStation", "main"]


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
    def init_device(self: MccsStation) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        super().init_device()

    def _init_state_model(self: MccsStation) -> None:
        super()._init_state_model()
        self._obs_state_model = StationObsStateModel(self.logger, self._update_obs_state)
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = StationHealthModel(
            self.APIUFQDN,
            self.AntennaFQDNs,
            self.TileFQDNs,
            self.health_changed,
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
            self.push_change_event,
            self._communication_status_changed,
            self._component_power_mode_changed,
            self._health_model.apiu_health_changed,
            self._health_model.antenna_health_changed,
            self._health_model.tile_health_changed,
            self._obs_state_model.is_configured_changed,
        )

    def init_command_objects(self: MccsStation) -> None:
        """Set up the handler objects for Commands."""
        super().init_command_objects()

        self.register_command_object(
            "Configure",
            self.ConfigureCommand(self.component_manager, self.op_state_model, self.logger),
        )
        self.register_command_object(
            "ApplyPointing",
            self.ApplyPointingCommand(self.component_manager, self.op_state_model, self.logger),
        )

    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.MccsStation`'s Init command.

        The :py:meth:`~.MccsStation.InitCommand.do` method below is
        called upon :py:class:`~.MccsStation`'s initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsStation.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the :py:class:`.MccsStation`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            (result_code, message) = super().do()
            device = self.target
            device._subarray_id = 0
            device._refLatitude = 0.0
            device._refLongitude = 0.0
            device._refHeight = 0.0
            device._beam_fqdns = []
            device._transient_buffer_fqdn = ""
            device._delay_centre = []
            device._calibration_coefficients = []
            device._is_calibrated = False
            device._calibration_job_id = 0
            device._daq_job_id = 0
            device._data_directory = ""

            device._build_state = release.get_release_info()
            device._version_id = release.version

            device.set_change_event("beamFQDNs", True, True)
            device.set_archive_event("beamFQDNs", True, True)
            device.set_change_event("transientBufferFQDN", True, False)
            device.set_archive_event("transientBufferFQDN", True, False)

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state
            return (result_code, message)

    class OnCommand(ResponseCommand):
        """
        A class for the MccsStation's On() command.

        This class overrides the SKABaseDevice OnCommand to allow for an
        eventual consistency semantics. This requires an override
        because the SKABaseDevice OnCommand only allows On() to be run
        when in OFF state.
        """

        def do(  # type: ignore[override]
            self: MccsStation.OnCommand,
        ) -> tuple[ResultCode, str]:
            """
            Stateless hook for Off() command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            # It's fine to complete this long-running command here
            # (returning ResultCode.OK), even though the component manager
            # may not actually be finished turning everything on.
            # The completion of the original On command to MccsController
            # is waiting for the various power mode callbacks to be received
            # rather than completion of the various long-running commands.
            _ = self.target.on()
            message = "Station On command completed OK"
            return (ResultCode.OK, message)

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
    def _communication_status_changed(
        self: MccsStation,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_status: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: None,  # wait for a power mode update
        }

        action = action_map[communication_status]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(communication_status == CommunicationStatus.ESTABLISHED)

    def _component_power_mode_changed(
        self: MccsStation,
        power_mode: PowerMode,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_mode: the power mode of the component.
        """
        action_map = {
            PowerMode.OFF: "component_off",
            PowerMode.STANDBY: "component_standby",
            PowerMode.ON: "component_on",
            PowerMode.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_mode])

    def health_changed(self: MccsStation, health: HealthState) -> None:
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    # Reimplementation for debugging purposes
    def _update_state(self: MccsStation, state: tango.DevState) -> None:
        """
        Update the device state.

        TODO: This is already implemented in
        :py:class:`ska_tango_base.base.SKABaseDevice`, and it should not
        be necessary to re-implement it here. However, updating state in
        this device is sometimes erroring for an unknown reason. These
        try-except clauses were added for diagnostics, but instead they
        seem to be magically fixing the problem. We need to develop an
        understanding of this issue.

        :param state: the new state of the device

        :raises Exception: for unknown reasons. This is a to-do.
        """
        try:
            current_state = self.get_state()
        except Exception as e:
            self.logger.error(f"Attempt to get state resulted in exception {e}")
            raise

        if state != current_state:
            try:
                self.set_state(state)
            except Exception as e:
                self.logger.error(f"Attempt to set state resulted in exception {e}")
                raise
            try:
                self.set_status(f"The device is in {state} state.")
            except Exception as e:
                self.logger.error(f"Attempt to set status resulted in exception {e}")
                raise
            self.logger.info(f"Device state changed from {self.get_state()} to {state}")

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
    class ConfigureCommand(ResponseCommand):
        """Class for handling the Configure() command."""

        SUCCEEDED_MESSAGE = "Configure command completed OK"
        FAILED_MESSAGE = "Configure command failed"

        def do(  # type: ignore[override]
            self: MccsStation.ConfigureCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement Configure() command functionality.

            :param argin: Configuration specification dict as a json string

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            configuration = json.loads(argin)
            station_id = configuration.get("station_id")
            component_manager = self.target
            try:
                result_code = component_manager.configure(station_id)
            except ValueError as value_error:
                return (ResultCode.FAILED, f"Configure command failed: {value_error}")

            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(
        dtype_in="DevString",
        dtype_out="DevVarLongStringArray",
    )
    def Configure(self: MccsStation, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the station with all relevant parameters.

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

    class ApplyPointingCommand(ResponseCommand):
        """Class for handling the ApplyPointing(argin) command."""

        SUCCEEDED_MESSAGE = "ApplyPointing command completed OK"
        FAILED_MESSAGE = "ApplyPointing command failed: ValueError in Tile"

        def do(  # type: ignore[override]
            self: MccsStation.ApplyPointingCommand, argin: list[float]
        ) -> tuple[ResultCode, str]:
            """
            Implement ApplyPointing command functionality.

            :param argin: an array containing a beam index and antenna
                delays

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            result_code = component_manager.apply_pointing(argin)
            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (ResultCode.FAILED, self.FAILED_MESSAGE)

    @command(
        dtype_in="DevVarDoubleArray",
        dtype_out="DevVarLongStringArray",
    )
    def ApplyPointing(self: MccsStation, argin: list[float]) -> DevVarLongStringArrayType:
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
