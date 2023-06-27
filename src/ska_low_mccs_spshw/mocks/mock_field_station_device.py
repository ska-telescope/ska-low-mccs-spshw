# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a mock Tango device for a FieldStation."""
from __future__ import annotations

from typing import Any, Optional

from ska_control_model import CommunicationStatus, ResultCode
from ska_tango_base.base import SKABaseDevice
from tango.server import attribute, command

from .mock_field_station_component_manager import MockFieldStationComponentManager

DevVarLongStringArrayType = tuple[list[ResultCode], list[Optional[str]]]

__all__ = ["MockFieldStation", "main"]


class MockFieldStation(SKABaseDevice):
    """An mocked implementation of the FieldStation Tango device."""

    INITIAL_MOCKED_OUTSIDE_TEMPERATURE = 42.5

    def create_component_manager(
        self: MockFieldStation,
    ) -> MockFieldStationComponentManager:
        """
        Create and return a mock component manager for this mock device.

        :return: a component manager for this device.
        """
        return MockFieldStationComponentManager(
            self.logger,
            self._component_communication_state_changed,
            self._component_state_changed,
        )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this mock device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        super().__init__(*args, **kwargs)
        self.outside_temperature = self.INITIAL_MOCKED_OUTSIDE_TEMPERATURE

    def init_device(self: MockFieldStation) -> None:
        """Initialise this mock device."""
        super().init_device()
        self.set_change_event("OutsideTemperature", True, False)

    def _component_communication_state_changed(
        self: MockFieldStation,
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
            CommunicationStatus.ESTABLISHED: "component_on",
        }

        action = action_map[communication_state]
        if action is not None:
            self.op_state_model.perform_action(action)

    # -----------------
    # Mocked Attributes
    # ----------------
    @attribute(
        dtype="float",
        label="outsideTemperature",
    )
    def outsideTemperature(self: MockFieldStation) -> float:
        """
        Return the mocked outside temperature.

        :return: the mocked outside temperature.
        """
        return self.outside_temperature

    # ---------------
    # Mocked Commands
    # ---------------
    @command(dtype_in="float", dtype_out="DevVarLongStringArray")
    def MockOutsideTemperatureChange(
        self: MockFieldStation, argin: float
    ) -> DevVarLongStringArrayType:
        """
        Mock a change in the outside temperature.

        :param argin: A float representing the mocked outside temperature.
        :return: A tuple containing a return code and a string message
                indicating status.
        """
        self.outside_temperature = argin
        self.push_change_event("outsideTemperature", argin)
        return ([ResultCode.OK], ["_"])


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
    return MockFieldStation.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
