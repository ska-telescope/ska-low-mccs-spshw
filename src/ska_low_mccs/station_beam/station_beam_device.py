# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS station beam device."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple, cast

import tango
from ska_control_model import CommunicationStatus, HealthState, ResultCode
from ska_low_mccs_common import release
from ska_tango_base.commands import SubmittedSlowCommand
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command, device_property

from ska_low_mccs.station_beam import (
    StationBeamComponentManager,
    StationBeamHealthModel,
)

__all__ = ["MccsStationBeam", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsStationBeam(SKAObsDevice):
    """An implementation of a station beam Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    BeamId = device_property(dtype=int, default_value=0)

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsStationBeam) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsStationBeam) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = StationBeamHealthModel(
            self._component_state_changed_callback
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsStationBeam,
    ) -> StationBeamComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return StationBeamComponentManager(
            self.BeamId,
            self.logger,
            self._max_workers,
            self._communication_state_changed,
            self._component_state_changed_callback,
        )

    def init_command_objects(self: MccsStationBeam) -> None:
        """Initialise the command handlers for commands supported by this device."""
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
                    logger=self.logger,
                ),
            )

    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.MccsStationBeam`'s Init command.

        The :py:meth:`~.MccsStationBeam.InitCommand.do` method below is
        called upon :py:class:`~.MccsStationBeam`'s initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsStationBeam.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsStationBeam.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            super().do()

            return (ResultCode.OK, "Initialisation complete")

    # ----------
    # Callbacks
    # ----------
    def _component_state_changed_callback(
        self: MccsStationBeam,
        state_change: dict[str, Any],
        fqdn: Optional[str] = None,
    ) -> None:
        """
        Handle change in this device's state.

        This is a callback hook, called whenever the state changes. It
        is responsible for updating the tango side of things i.e. making
        sure the attribute is up to date, and events are pushed.

        :param state_change: A dictionary containing the name of the state that changed and its new value.
        :param fqdn: The fqdn of the calling device or `None` if this device is the caller.
        """
        if "health_state" in state_change.keys():
            health = cast(HealthState, state_change.get("health_state"))
            if fqdn is None:
                # Do regular health update. This device called the callback.
                if self._health_state != health:
                    self._health_state = health
                    self.push_change_event("healthState", health)
            else:
                # Call station health changed.
                self._health_model.station_health_changed(health)

        # Probably more to do here with fault.
        if "fault" in state_change.keys():
            station_fault = cast(bool, state_change.get("fault"))
            self._health_model.station_fault_changed(station_fault)

        if "beam_locked" in state_change.keys():
            beam_locked = cast(bool, state_change.get("beam_locked"))
            self._health_model.is_beam_locked_changed(beam_locked)

    def _communication_state_changed(
        self: MccsStationBeam,
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
            CommunicationStatus.ESTABLISHED: "component_on",  # it's an always-on device
        }

        self.op_state_model.perform_action(action_map[communication_state])
        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevLong", format="%i")
    def subarrayId(self: MccsStationBeam) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self.component_manager.subarray_id

    @subarrayId.write  # type: ignore[no-redef]
    def subarrayId(self: MccsStationBeam, subarray_id: int) -> None:
        """
        Set the subarray ID.

        :param subarray_id: The ID of the subarray this beam is assigned to
        """
        self.component_manager.subarray_id = subarray_id

    @attribute(dtype="DevLong", format="%i", max_value=47, min_value=0)
    def beamId(self: MccsStationBeam) -> int:
        """
        Return the station beam id.

        :return: the station beam id
        """
        return self.component_manager.beam_id

    @attribute(dtype=str)
    def stationFqdn(self: MccsStationBeam) -> str:
        """
        Return the station FQDN.

        :return: the station FQDN
        """
        return self.component_manager.station_fqdn

    @stationFqdn.write  # type: ignore[no-redef]
    def stationFqdn(self: MccsStationBeam, station_fqdn: str) -> None:
        """
        Set the station FQDN.

        :param station_fqdn: FQDN of the station for this beam
        """
        self.component_manager.station_fqdn = station_fqdn

    @attribute(dtype="DevLong")
    def stationId(self: MccsStationBeam) -> int:
        """
        Return the station id.

        :return: the station id
        """
        return self.component_manager.station_id

    @stationId.write  # type: ignore[no-redef]
    def stationId(self: MccsStationBeam, station_id: int) -> None:
        """
        Set the station id.

        :param station_id: id of the station for this beam
        """
        self.component_manager.station_id = station_id

    @attribute(dtype="DevLong", format="%i", max_value=7, min_value=0)
    def logicalBeamId(self: MccsStationBeam) -> int:
        """
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        """
        return self.component_manager.logical_beam_id

    @logicalBeamId.write  # type: ignore[no-redef]
    def logicalBeamId(self: MccsStationBeam, logical_beam_id: int) -> None:
        """
        Set the logical beam id.

        :param logical_beam_id: the logical beam id
        """
        self.component_manager.logical_beam_id = logical_beam_id

    @attribute(
        dtype="DevDouble",
        unit="Hz",
        standard_unit="s^-1",
        max_value=1e37,
        min_value=0,
    )
    def updateRate(self: MccsStationBeam) -> float:
        """
        Return the update rate (in hertz) for this station beam.

        :return: the update rate for this station beam
        """
        return self.component_manager.update_rate

    @attribute(dtype="DevBoolean")
    def isBeamLocked(self: MccsStationBeam) -> bool:
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        """
        return self.component_manager.is_beam_locked

    @isBeamLocked.write  # type: ignore[no-redef]
    def isBeamLocked(self: MccsStationBeam, value: bool) -> None:
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        """
        self.component_manager.is_beam_locked = value

    @attribute(dtype=(("DevLong",),), max_dim_y=384, max_dim_x=4)
    def channels(self: MccsStationBeam) -> list[list[int]]:
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        """
        return self.component_manager.channels

    @attribute(dtype=("DevFloat",), max_dim_x=384)
    def antennaWeights(self: MccsStationBeam) -> list[float]:
        """
        Return the antenna weights configured for this beam.

        :return: antenna weightd
        """
        return self.component_manager.antenna_weights

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def desiredPointing(self: MccsStationBeam) -> list[float]:
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam, conforming to the Sky Coordinate Set definition
        """
        return self.component_manager.desired_pointing

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
        self.component_manager.desired_pointing = values

    @attribute(dtype=("DevDouble",), max_dim_x=384)
    def pointingDelay(self: MccsStationBeam) -> list[float]:
        """
        Return the pointing delay of this beam.

        :return: the pointing delay of this beam
        """
        return self.component_manager.pointing_delay

    @pointingDelay.write  # type: ignore[no-redef]
    def pointingDelay(self: MccsStationBeam, values: list[float]) -> None:
        """
        Set the pointing delay of this beam.

        :param values: the pointing delay of this beam
        """
        self.component_manager.pointing_delay = values

    @attribute(dtype=("DevDouble",), max_dim_x=384)
    def pointingDelayRate(self: MccsStationBeam) -> list[float]:
        """
        Return the pointing delay rate of this beam.

        :return: the pointing delay rate of this beam
        """
        return self.component_manager.pointing_delay_rate

    @pointingDelayRate.write  # type: ignore[no-redef]
    def pointingDelayRate(self: MccsStationBeam, values: list[float]) -> None:
        """
        Set the pointing delay rate of this beam.

        :param values: the pointing delay rate of this beam
        """
        self.component_manager.pointing_delay_rate = values

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def phaseCentre(self: MccsStationBeam) -> list[float]:
        """
        Return the phase centre.

        :return: the phase centre
        """
        return self.component_manager.phase_centre

    # --------
    # Commands
    # --------
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(self: MccsStationBeam, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the station_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Configure")
        (result_code, unique_id) = handler(argin)
        return ([result_code], [unique_id])

    @command(dtype_out="DevVarLongStringArray")
    def ApplyPointing(self: MccsStationBeam) -> DevVarLongStringArrayType:
        """
        Apply pointing delays to antennas associated with the station_beam.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("ApplyPointing")
        (result_code, unique_id) = handler()
        return ([result_code], [unique_id])


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
    return MccsStationBeam.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
