# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS tel state device."""
from __future__ import annotations

from typing import Any

import tango
from ska_tango_base import SKATelState
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import CommunicationStatus, HealthState
from tango.server import attribute

import ska_low_mccs.release as release
from ska_low_mccs.tel_state import TelStateComponentManager, TelStateHealthModel

__all__ = ["MccsTelState", "main"]


class MccsTelState(SKATelState):
    """An implementation of a tel state Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsTelState) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        super().init_device()

    def _init_state_model(self: MccsTelState) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TelStateHealthModel(self.component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsTelState,
    ) -> TelStateComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return TelStateComponentManager(
            self.logger,
            self._max_workers,
            self._component_communication_state_changed,
            self.component_state_changed_callback,
        )

    class InitCommand(SKATelState.InitCommand):
        """Class that implements device initialisation for this device."""

        def do(  # type:ignore[override]
            self: MccsTelState.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise TelState device.

            Initialises the attributes and
            properties of the :py:class:`.MccsTelState` device.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            super().do()
            self._device._build_state = release.get_release_info()
            self._device._version_id = release.version

            return (ResultCode.OK, "Init command completed OK")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_state_changed(
        self: MccsTelState,
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
        self: MccsTelState, state_change: dict[str, Any]
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
    @attribute(dtype="DevString")
    def elementsStates(self: MccsTelState) -> str:
        """
        Return the elementsStates attribute.

        :todo: What is this?

        :return: the elementsStates attribute
        """
        return self.component_manager.elements_states

    @elementsStates.write  # type: ignore[no-redef]
    def elementsStates(self: MccsTelState, value: str) -> None:
        """
        Set the elementsStates attribute.

        :todo: What is this?

        :param value: the new elementsStates attribute value
        """
        self.component_manager.elements_states = value

    @attribute(dtype="DevString")
    def observationsStates(self: MccsTelState) -> str:
        """
        Return the observationsStates attribute.

        :todo: What is this?

        :return: the observationsStates attribute
        """
        return self.component_manager.observations_states

    @observationsStates.write  # type: ignore[no-redef]
    def observationsStates(self: MccsTelState, value: str) -> None:
        """
        Set the observationsStates attribute.

        :todo: What is this?

        :param value: the new observationsStates attribute value
        """
        self.component_manager.observations_states = value

    @attribute(dtype="DevString")
    def algorithms(self: MccsTelState) -> str:
        """
        Return the algorithms attribute.

        :todo: What is this? TBD

        :return: the algorithms attribute
        """
        return self.component_manager.algorithms

    @algorithms.write  # type: ignore[no-redef]
    def algorithms(self: MccsTelState, value: str) -> None:
        """
        Set the algorithms attribute.

        :todo: What is this? TBD

        :param value: the new value for the algorithms attribute
        """
        self.component_manager.algorithms = value

    @attribute(dtype="DevString")
    def algorithmsVersion(self: MccsTelState) -> str:
        """
        Return the algorithm version.

        :return: the algorithm version
        """
        return self.component_manager.algorithms_version

    @algorithmsVersion.write  # type: ignore[no-redef]
    def algorithmsVersion(self: MccsTelState, value: str) -> None:
        """
        Set the algorithm version.

        :param value: the new value for the algorithm version
        """
        self.component_manager.algorithms_version = value


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
    return MccsTelState.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()