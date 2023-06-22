# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a Tango device for a Calibration Store."""
from __future__ import annotations

import json

from ska_control_model import CommunicationStatus
from ska_tango_base.base import SKABaseDevice
from tango.server import command

from .calibration_store_component_manager import CalibrationStoreComponentManager

__all__ = ["MccsCalibrationStore", "main"]


class MccsCalibrationStore(SKABaseDevice):
    """An implementation of the CalibrationStore Tango device."""

    def create_component_manager(
        self: MccsCalibrationStore,
    ) -> CalibrationStoreComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return CalibrationStoreComponentManager(
            self.logger,
            self._component_communication_state_changed,
            self._component_state_changed,
        )

    def init_device(self: MccsCalibrationStore) -> None:
        """Initialise this mock device."""
        super().init_device()

    def _component_communication_state_changed(
        self: MccsCalibrationStore,
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

    @command(dtype_in="DevString", dtype_out="DevVarDoubleArray")
    def GetSolution(self: MccsCalibrationStore, argin: str) -> list[float]:
        """
        Get a calibration from the calibration store.

        :param argin: json-dictionary of field conditions.

        :return: a calibration from the calibration store.
        """
        # TODO: implement this properly, including a schema for json validation
        # and reading solutions from a db
        args = json.loads(argin)
        input_vars = [args["outside_temperature"], args["channel"]]
        return input_vars + list(range(254))


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
    return MccsCalibrationStore.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
