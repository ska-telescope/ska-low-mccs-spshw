#  -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS transient buffer device."""
from __future__ import annotations

import importlib
import json
import logging
from typing import Any, Final, Optional

from ska_control_model import CommunicationStatus, HealthState, ResultCode
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import FastCommand, JsonValidator
from tango.server import command, device_property

from .station_calibrator_component_manager import StationCalibratorComponentManager
from .station_calibrator_health_model import StationCalibratorHealthModel

__all__ = ["MccsStationCalibrator", "main"]


class MccsStationCalibrator(SKABaseDevice):
    """An implementation of a station calibrator Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    FieldStationName = device_property(
        dtype=str,
        mandatory=True,
        doc="The name of the Field Station to get field information from.",
    )
    CalibrationStoreName = device_property(
        dtype=str,
        mandatory=True,
        doc="The name of the Calibration Store to get calibrations from.",
    )

    # ---------------
    # Initialisation
    # ---------------
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

        self.component_manager: StationCalibratorComponentManager
        self._health_state: HealthState = HealthState.UNKNOWN
        self._health_model: StationCalibratorHealthModel

    def _init_state_model(self: MccsStationCalibrator) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = StationCalibratorHealthModel(
            self._health_changed,
            ignore_power_state=True,
        )
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsStationCalibrator,
    ) -> StationCalibratorComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return StationCalibratorComponentManager(
            self.logger,
            self.FieldStationName,
            self.CalibrationStoreName,
            self._component_communication_state_changed,
            self._component_state_callback,
        )

    def init_command_objects(self: MccsStationCalibrator) -> None:
        """Initialise the command handlers for this device."""
        super().init_command_objects()
        for command_name, command_object in [
            ("GetCalibration", self.GetCalibrationCommand),
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
        A class for :py:class:`~.MccsStationCalibrator`'s Init command.

        The :py:meth:`~.MccsStationCalibrator.InitCommand.do` method below
        is called upon :py:class:`~.MccsStationCalibrator`'s
        initialisation.
        """

        def do(  # type: ignore[override]
            self: MccsStationCalibrator.InitCommand,
            *args: Any,
            **kwargs: Any,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsStationCalibrator.

            :param args: positional args to the component manager method
            :param kwargs: keyword args to the component manager method

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            return super().do(*args, **kwargs)

    # ----------
    # Callbacks
    # ----------
    def _component_communication_state_changed(
        self: MccsStationCalibrator,
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

    def _component_state_callback(self: MccsStationCalibrator, **kwargs: Any) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param kwargs: dictionary of state change parameters.
        """
        self.logger.debug("State change received")

    def _health_changed(self: MccsStationCalibrator, health: HealthState) -> None:
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

    # ----------
    # Commands
    # ----------
    class GetCalibrationCommand(FastCommand):
        # pylint: disable=line-too-long
        """
        Class for handling the GetCalibration() command.

        This command takes as input a JSON string that conforms to the
        following schema:

        .. literalinclude:: /../../src/ska_low_mccs_spshw/station_calibrator/schemas/MccsStationCalibrator_GetCalibration.json
           :language: json
        """  # noqa: E501

        SCHEMA: Final = json.loads(
            importlib.resources.read_text(
                "ska_low_mccs_spshw.station_calibrator.schemas",
                "MccsStationCalibrator_GetCalibration.json",
            )
        )

        def __init__(
            self: MccsStationCalibrator.GetCalibrationCommand,
            component_manager: StationCalibratorComponentManager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param component_manager: the device's component manager
            :param logger: a logger for this command to log with.
            """
            self._component_manager = component_manager
            validator = JsonValidator("GetCalibration", self.SCHEMA, logger)
            super().__init__(logger, validator)

        def do(
            self: MccsStationCalibrator.GetCalibrationCommand,
            *args: Any,
            **kwargs: Any,
        ) -> list[float]:
            """
            Implement :py:meth:`.MccsStationCalibrator.GetCalibration` command.

            :param args: Positional arguments. This should be empty and
                is provided for type hinting purposes only.
            :param kwargs: keyword arguments unpacked from the JSON
                argument to the command.

            :return: a calibration from the calibration store.
            """
            frequency_channel = kwargs["frequency_channel"]
            return self._component_manager.get_calibration(frequency_channel)

    @command(dtype_in="DevString", dtype_out="DevVarDoubleArray")
    def GetCalibration(self: MccsStationCalibrator, argin: str) -> list[float]:
        """
        Get a calibration from the calibration store.

        :param argin: json-dictionary of field conditions.

        :return: a calibration from the calibration store.
        """
        handler = self.get_command_object("GetCalibration")
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
    return MccsStationCalibrator.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
