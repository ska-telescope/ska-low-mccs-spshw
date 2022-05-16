# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS subarray beam device."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

import tango
from ska_tango_base.commands import DeviceInitCommand, ResultCode, SubmittedSlowCommand
from ska_tango_base.control_model import CommunicationStatus, HealthState
from ska_tango_base.obs import SKAObsDevice
from tango.server import attribute, command

from ska_low_mccs import release
from ska_low_mccs.subarray_beam import (
    SubarrayBeamComponentManager,
    SubarrayBeamHealthModel,
    SubarrayBeamObsStateModel,
)

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]

__all__ = ["MccsSubarrayBeam", "main"]


class MccsSubarrayBeam(SKAObsDevice):
    """An implementation of a subarray beam Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsSubarrayBeam) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsSubarrayBeam) -> None:
        super()._init_state_model()
        self._obs_state_model = SubarrayBeamObsStateModel(
            self.logger, self.component_state_changed_callback
        )
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubarrayBeamHealthModel(
            self.component_state_changed_callback
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsSubarrayBeam,
    ) -> SubarrayBeamComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return SubarrayBeamComponentManager(
            self.logger,
            self._max_workers,
            self._component_communication_state_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsSubarrayBeam) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("Configure", "configure"),
            ("Scan", "scan"),
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

    class InitCommand(DeviceInitCommand):
        """
        A class for :py:class:`~.MccsSubarrayBeam`'s Init command.

        The :py:meth:`~.MccsSubarrayBeam.InitCommand.do` method below is
        called upon :py:class:`~.MccsSubarrayBeam`'s initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsSubarrayBeam.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsSubarrayBeam.

            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to the OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            return (ResultCode.OK, "Initialisation complete")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_state_changed(
        self: MccsSubarrayBeam,
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
            CommunicationStatus.ESTABLISHED: "component_on",  # always-on device
        }

        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_state == CommunicationStatus.ESTABLISHED
        )

    def component_state_changed_callback(
        self: MccsSubarrayBeam, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: the state change dict
        """
        print("callback called")
        print("callback called with: ", state_change)
        if "health_state" in state_change.keys():
            health = state_change["health_state"]
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

        if "beam_locked" in state_change.keys():
            beam_locked = state_change["beam_locked"]
            self._health_model.is_beam_locked_changed(beam_locked)

        if "configured_changed" in state_change.keys():
            configured_changed = state_change["configured_changed"]
            self._obs_state_model.is_configured_changed(configured_changed)

            if "obs_state" in state_change.keys():
                configured_changed = state_change.get("obs_state")
                self._obs_state_model.obs_state = configured_changed

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevLong", format="%i")
    def subarrayId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self.component_manager.subarray_id

    @attribute(dtype="DevLong", format="%i", max_value=47, min_value=0)
    def subarrayBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray beam id.

        :return: the subarray beam id
        """
        return self.component_manager.subarray_beam_id

    @attribute(dtype=("DevLong",), format="%i", max_value=47, min_value=0)
    def stationBeamIds(self: MccsSubarrayBeam) -> list[int]:
        """
        Return the ids of station beams assigned to this subarray beam.

        :return: the station beam ids
        """
        return self.component_manager.station_beam_ids

    @stationBeamIds.write  # type: ignore[no-redef]
    def stationBeamIds(self: MccsSubarrayBeam, station_beam_ids: list[int]) -> None:
        """
        Set the station beam ids.

        :param station_beam_ids: ids of the station beams for this subarray beam
        """
        self.component_manager.station_beam_ids = station_beam_ids

    @attribute(dtype=("DevLong",), max_dim_x=512, format="%i")
    def stationIds(self: MccsSubarrayBeam) -> list[int]:
        """
        Return the station ids.

        :return: the station ids
        """
        return self.component_manager.station_ids

    @stationIds.write  # type: ignore[no-redef]
    def stationIds(self: MccsSubarrayBeam, station_ids: list[int]) -> None:
        """
        Set the station ids.

        :param station_ids: ids of the stations for this beam
        """
        self.component_manager.station_ids = station_ids

    @attribute(dtype="DevLong", format="%i", max_value=7, min_value=0)
    def logicalBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        """
        return self.component_manager.logical_beam_id

    @logicalBeamId.write  # type: ignore[no-redef]
    def logicalBeamId(self: MccsSubarrayBeam, logical_beam_id: int) -> None:
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
    def updateRate(self: MccsSubarrayBeam) -> float:
        """
        Return the update rate (in hertz) for this subarray beam.

        :return: the update rate for this subarray beam
        """
        return self.component_manager.update_rate

    @attribute(dtype="DevBoolean")
    def isBeamLocked(self: MccsSubarrayBeam) -> bool:
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        """
        return self.component_manager.is_beam_locked

    @isBeamLocked.write  # type: ignore[no-redef]
    def isBeamLocked(self: MccsSubarrayBeam, value: bool) -> None:
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        """
        self.component_manager.is_beam_locked = value

    @attribute(dtype=(("DevLong",),), max_dim_y=384, max_dim_x=4)
    def channels(self: MccsSubarrayBeam) -> list[list[int]]:
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        """
        return self.component_manager.channels

    @attribute(dtype=("DevFloat",), max_dim_x=384)
    def antennaWeights(self: MccsSubarrayBeam) -> list[float]:
        """
        Return the antenna weights configured for this beam.

        :return: antenna weightd
        """
        return self.component_manager.antenna_weights

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def desiredPointing(self: MccsSubarrayBeam) -> list[float]:
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam, conforming to the Sky Coordinate Set definition
        """
        return self.component_manager.desired_pointing

    @desiredPointing.write  # type:ignore[no-redef]
    def desiredPointing(self: MccsSubarrayBeam, values: list[float]) -> None:
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

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def phaseCentre(self: MccsSubarrayBeam) -> list[float]:
        """
        Return the phase centre.

        :return: the phase centre
        """
        return self.component_manager.phase_centre

    # --------
    # Commands
    # --------
    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(self: MccsSubarrayBeam, argin: str) -> DevVarLongStringArrayType:
        """
        Configure the subarray_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Configure")
        (result_code, unique_id) = handler(argin)
        return ([result_code], [unique_id])

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Scan(self: MccsSubarrayBeam, argin: str) -> DevVarLongStringArrayType:
        """
        Start a scan on the subarray_beam.

        :param argin: Scan parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Scan")
        (result_code, unique_id) = handler(argin)
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
    return MccsSubarrayBeam.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
