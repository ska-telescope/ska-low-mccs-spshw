# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS transient buffer device."""
from __future__ import annotations

from typing import Any

import tango
from ska_control_model import CommunicationStatus, HealthState, ResultCode
from ska_low_mccs_common import release
from ska_tango_base.base import SKABaseDevice
from tango.server import attribute

from ska_low_mccs.transient_buffer import (
    TransientBufferComponentManager,
    TransientBufferHealthModel,
)

__all__ = ["MccsTransientBuffer", "main"]


class MccsTransientBuffer(SKABaseDevice):
    """An implementation of a transient buffer Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsTransientBuffer) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsTransientBuffer) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TransientBufferHealthModel(
            self.component_state_changed_callback
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsTransientBuffer,
    ) -> TransientBufferComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return TransientBufferComponentManager(
            self.logger,
            self._max_workers,
            self._component_communication_state_changed,
            self.component_state_changed_callback,
        )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        A class for :py:class:`~.MccsTransientBuffer`'s Init command.

        The :py:meth:`~.MccsTransientBuffer.InitCommand.do` method below
        is called upon :py:class:`~.MccsTransientBuffer`'s
        initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsTransientBuffer.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsTransientBuffer.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            # super().do()
            self._build_state = release.get_release_info()
            self._version_id = release.version

            return (ResultCode.OK, "Init command completed OK")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_state_changed(
        self: MccsTransientBuffer,
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
        self: MccsTransientBuffer, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: dictionary of state change parameters.
        """
        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevString", label="stationId")
    def stationId(self: MccsTransientBuffer) -> int:
        """
        Return the station id.

        :return: the station id
        """
        return self.component_manager.station_id

    @attribute(dtype="DevString", label="transientBufferJobId")
    def transientBufferJobId(self: MccsTransientBuffer) -> int:
        """
        Return the transient buffer job id.

        :return: the transient buffer job id
        """
        return self.component_manager.transient_buffer_job_id

    @attribute(dtype="DevLong", label="resamplingBits")
    def resamplingBits(self: MccsTransientBuffer) -> int:
        """
        Return the resampling bit depth.

        :return: the resampling bit depth
        """
        return self.component_manager.resampling_bits

    @attribute(dtype="DevShort", label="nStations")
    def nStations(self: MccsTransientBuffer) -> int:
        """
        Return the number of stations.

        :return: the number of stations
        """
        return self.component_manager.n_stations

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=100,
        label="transientFrequencyWindow",
    )
    def transientFrequencyWindow(self: MccsTransientBuffer) -> list[float]:
        """
        Return the transient frequency window.

        :return: the transient frequency window
        """
        return self.component_manager.transient_frequency_window

    @attribute(dtype=("DevString",), max_dim_x=100, label="stationIds")
    def stationIds(self: MccsTransientBuffer) -> list[str]:
        """
        Return the station ids.

        :return: the station ids
        """
        return self.component_manager.station_ids


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
    return MccsTransientBuffer.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
