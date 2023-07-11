# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides a Tango device for a Calibration Store."""
from __future__ import annotations

import importlib
import json
import logging
from typing import Any, Final, Optional

from ska_control_model import CommunicationStatus, HealthState, ResultCode
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import FastCommand, JsonValidator
from tango.server import command, device_property

from .calibration_store_component_manager import CalibrationStoreComponentManager
from .calibration_store_health_model import CalibrationStoreHealthModel

__all__ = ["MccsCalibrationStore", "main"]

DevVarLongStringArrayType = tuple[list[ResultCode], list[str]]


class MccsCalibrationStore(SKABaseDevice):
    """An implementation of the CalibrationStore Tango device."""

    DatabaseHost = device_property(dtype=str, default_value="test-postgresql")
    DatabasePort = device_property(dtype=int, default_value=5432)
    DatabaseName = device_property(dtype=str, default_value="postgres")
    DatabaseAdminUser = device_property(dtype=str, default_value="postgres")
    DatabaseAdminPassword = device_property(dtype=str, default_value="")

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
        # "attribute-defined-outside-init" etc.
        super().__init__(*args, **kwargs)

        self.component_manager: CalibrationStoreComponentManager
        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: CalibrationStoreHealthModel

    def _init_state_model(self: MccsCalibrationStore) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = CalibrationStoreHealthModel(self._health_changed)
        self.set_change_event("healthState", True, False)

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
            self.DatabaseHost,
            self.DatabasePort,
            self.DatabaseName,
            self.DatabaseAdminUser,
            self.DatabaseAdminPassword,
        )

    def init_command_objects(self: MccsCalibrationStore) -> None:
        """Initialise the command handlers for this device."""
        super().init_command_objects()
        for command_name, command_object in [
            ("GetSolution", self.GetSolutionCommand),
            ("StoreSolution", self.StoreSolutionCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(
                    self.component_manager,
                    logger=self.logger,
                ),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """
        A class for :py:class:`~.MccsCalibrationStore`'s Init command.

        The :py:meth:`~.MccsCalibrationStore.InitCommand.do` method below
        is called upon :py:class:`~.MccsCalibrationStore`'s
        initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsCalibrationStore.InitCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsCalibrationStore.

            :param args: positional args to the component manager method
            :param kwargs: keyword args to the component manager method

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            return super().do(*args, **kwargs)

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

        self._health_model.update_state(
            communicating=(communication_state == CommunicationStatus.ESTABLISHED)
        )

    def _health_changed(self: MccsCalibrationStore, health: HealthState) -> None:
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

    class GetSolutionCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the GetSolution() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/calibration_store/schemas/MccsCalibrationStore_GetSolution.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.calibration_store.schemas",
                "MccsCalibrationStore_GetSolution.json",
            )
        )

        def __init__(
            self: MccsCalibrationStore.GetSolutionCommand,
            component_manager: CalibrationStoreComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param component_manager: the device's component manager
            :param logger: a logger for this command to log with.
            """
            self._component_manager = component_manager
            validator = JsonValidator("GetSolution", self.SCHEMA, logger)
            super().__init__(logger, validator)

        def do(
            self: MccsCalibrationStore.GetSolutionCommand,
            *args: Any,
            **kwargs: Any,
        ) -> list[float]:
            """
            Implement :py:meth:`.MccsCalibrationStore.GetSolution` command.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: a calibration solution from the database.
            """
            frequency_channel = kwargs["frequency_channel"]
            outside_temperature = kwargs["outside_temperature"]
            return self._component_manager.get_solution(
                frequency_channel, outside_temperature
            )

    @command(dtype_in="DevString", dtype_out="DevVarDoubleArray")
    def GetSolution(self: MccsCalibrationStore, argin: str) -> list[float]:
        """
        Get a calibration solution from the database.

        :param argin: json-dictionary of field conditions and channel data.

        :return: a calibration solution from the database.
        """
        handler = self.get_command_object("GetSolution")
        return handler(argin)

    class StoreSolutionCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the StoreSolution() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/calibration_store/schemas/MccsCalibrationStore_StoreSolution.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.calibration_store.schemas",
                "MccsCalibrationStore_StoreSolution.json",
            )
        )

        def __init__(
            self: MccsCalibrationStore.StoreSolutionCommand,
            component_manager: CalibrationStoreComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param component_manager: the device's component manager
            :param logger: a logger for this command to log with.
            """
            self._component_manager = component_manager
            validator = JsonValidator("StoreSolution", self.SCHEMA, logger)
            super().__init__(logger, validator)

        def do(
            self: MccsCalibrationStore.StoreSolutionCommand,
            *args: Any,
            **kwargs: Any,
        ) -> DevVarLongStringArrayType:
            """
            Implement :py:meth:`.MccsCalibrationStore.StoreSolution` command.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: A tuple containing a return code and a string
                   message indicating status. The message is for
                   information purpose only.
            """
            frequency_channel = kwargs["frequency_channel"]
            outside_temperature = kwargs["outside_temperature"]
            solution = kwargs["solution"]
            return self._component_manager.store_solution(
                solution, frequency_channel, outside_temperature
            )

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def StoreSolution(
        self: MccsCalibrationStore, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Store a solution in the database.

        :param argin: json-dictionary of solution, field conditions and channel data.

        :return: tuple of result code and message.
        """
        handler = self.get_command_object("StoreSolution")
        return handler(argin)


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
