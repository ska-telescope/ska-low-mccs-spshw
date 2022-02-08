# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS transient buffer device."""
from __future__ import annotations

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState
from tango.server import attribute

from ska_low_mccs import release
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.transient_buffer import TransientBufferComponentManager, TransientBufferHealthModel

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
        super().init_device()

    def _init_state_model(self: MccsTransientBuffer) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TransientBufferHealthModel(self.health_changed)
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
            self.push_change_event,
            self._component_communication_status_changed,
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
            device = self.target

            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return super().do()

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsTransientBuffer,
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

    def health_changed(self: MccsTransientBuffer, health: HealthState) -> None:
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
