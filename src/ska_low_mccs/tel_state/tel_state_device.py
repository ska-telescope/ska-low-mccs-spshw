# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements the MCCS tel state device."""
from __future__ import annotations

import tango
from tango.server import attribute


from ska_tango_base import SKATelState
from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import HealthState

import ska_low_mccs.release as release

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.tel_state import (
    TelStateComponentManager,
    TelStateHealthModel,
)

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
        super().init_device()

    def _init_state_model(self: MccsTelState) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = TelStateHealthModel(self.health_changed)
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
            self._component_communication_status_changed,
            self._message_queue_size_changed,
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
            device = self.target
            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return (ResultCode.OK, "Init command completed OK")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsTelState,
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

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def _message_queue_size_changed(
        self: MccsTelState,
        size: int,
    ) -> None:
        """
        Handle change in component manager message queue size.

        :param size: the new size of the component manager's message
            queue
        """
        # TODO: This should push an event but the details have to wait for SP-1827
        self.logger.info(f"Message queue size is now {size}")

    def health_changed(self: MccsTelState, health: HealthState) -> None:
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
