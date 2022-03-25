# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS APIU device."""

from __future__ import annotations  # allow forward references in type hints

import threading
from typing import List, Optional, Tuple

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import (
    DeviceInitCommand,
    FastCommand,
    ResultCode,
    SubmittedSlowCommand,
)
from ska_tango_base.control_model import (
    CommunicationStatus,
    HealthState,
    PowerState,
    SimulationMode,
)
from tango.server import attribute, command, device_property

from ska_low_mccs.apiu import ApiuComponentManager, ApiuHealthModel

__all__ = ["MccsAPIU", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


class MccsAPIU(SKABaseDevice):
    """An implementation of an APIU Tango device for MCCS."""

    # -----------------
    # Device Properties
    # -----------------
    AntennaFQDNs = device_property(dtype=(str,), default_value=[])

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsAPIU) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        self._power_state_lock = threading.RLock()
        super().init_device()

    def _init_state_model(self: MccsAPIU) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = ApiuHealthModel(self.component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsAPIU,
    ) -> ApiuComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return ApiuComponentManager(
            SimulationMode.TRUE,
            len(self.AntennaFQDNs),
            self.logger,
            self._max_workers,
            self._component_communication_status_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsAPIU) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("PowerUpAntenna", "turn_on_antenna"),
            ("PowerDownAntenna", "turn_off_antenna"),
            ("PowerUp", "turn_on_antennas"),
            ("PowerDown", "turn_off_antennas"),
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
        self.register_command_object(
            "IsAntennaOn",
            self.IsAntennaOnCommand(self.component_manager, self.logger),
        )

    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS APIU device."""

        def do(self: MccsAPIU.InitCommand) -> tuple[ResultCode, str]:  # type: ignore[override]
            """
            Initialise the attributes and properties of the :py:class:`.MccsAPIU`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.health_changed
            """
            self._device._are_antennas_on = None
            self._device.set_change_event("areAntennasOn", True, False)

            self._device._isAlive = True
            self._device._overCurrentThreshold = 0.0
            self._device._overVoltageThreshold = 0.0
            self._device._humidityThreshold = 0.0

            return (ResultCode.OK, "Init command completed OK")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsAPIU,
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

    def component_state_changed_callback(
        self: MccsAPIU, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param kwargs: the state change parameters.
        """
        action_map = {
            PowerState.OFF: "component_off",
            PowerState.STANDBY: "component_standby",
            PowerState.ON: "component_on",
            PowerState.UNKNOWN: "component_unknown",
        }
        with self._power_state_lock:
            if "power_state" in state_change.keys():
                power_state = state_change.get("power_state")
                self.component_manager.power_state = power_state
                if power_state:
                    self.op_state_model.perform_action(action_map[power_state])

        if "fault" in state_change.keys():
            is_fault = state_change.get("fault")
            if is_fault:
                self.op_state_model.perform_action("component_fault")
                self._health_model.component_fault(True)
            else:
                self.op_state_model.perform_action(
                    action_map[self.component_manager.power_state]
                )
                self._health_model.component_fault(False)

        if "health_state" in state_change.keys():
            health = state_change.get("health_state")
            if self._health_state != health:
                self._health_state = health
                self.push_change_event("healthState", health)

        if "are_antennas_on" in state_change.keys():
            self._are_antennas_on: list[bool]  # typehint only
            are_antennas_on = state_change.get("are_antennas_on")
            if self._are_antennas_on != are_antennas_on:
                self._are_antennas_on = list(are_antennas_on)
                self.push_change_event("areAntennasOn", self._are_antennas_on)

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype=SimulationMode,
        memorized=True,
        hw_memorized=True,
    )
    def simulationMode(self: MccsAPIU):
        """
        Report the simulation mode of the device.

        :return: the current simulation mode
        """
        return self.component_manager.simulation_mode

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(self: MccsAPIU, value: SimulationMode) -> None:
        """
        Set the simulation mode.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.component_manager.simulation_mode = value

    @attribute(dtype=int, label="antennas count")
    def antennaCount(self: MccsAPIU) -> int:
        """
        Return the number of antennas connected to this APIU.

        :return: the number of antennas connected to this APIU
        """
        return self.component_manager.antenna_count

    @attribute(dtype=(bool,), max_dim_x=256, label="Are Antennas On")
    def areAntennasOn(self: MccsAPIU) -> list[bool]:
        """
        Return whether each antenna is powered or not.

        :return: whether each antenna is powered or not
        """
        return self.component_manager.are_antennas_on()

    @attribute(dtype="DevDouble", label="Voltage", unit="Volts")
    def voltage(self: MccsAPIU) -> float:
        """
        Return the voltage attribute.

        :return: the voltage attribute
        """
        return self.component_manager.voltage

    @attribute(dtype="DevDouble", label="Current", unit="Amps")
    def current(self: MccsAPIU) -> float:
        """
        Return the current attribute.

        :return: the current value of the current attribute
        """
        return self.component_manager.current

    @attribute(dtype="DevDouble", label="Temperature", unit="degC")
    def temperature(self: MccsAPIU) -> float:
        """
        Return the temperature attribute.

        :return: the value of the temperature attribute
        """
        return self.component_manager.temperature

    @attribute(
        dtype="DevDouble",
        label="Humidity",
        unit="percent",
    )
    def humidity(self: MccsAPIU) -> float:
        """
        Return the humidity attribute.

        :return: the value of the humidity attribute
        """
        return self.component_manager.humidity

    @attribute(dtype="DevBoolean", label="Is alive?")
    def isAlive(self: MccsAPIU) -> bool:
        """
        Return the isAlive attribute.

        :return: the value of the isAlive attribute
        """
        return self._isAlive

    @attribute(dtype="DevDouble", label="Over current threshold", unit="Amp")
    def overCurrentThreshold(self: MccsAPIU) -> float:
        """
        Return the overCurrentThreshold attribute.

        :return: the value of the overCurrentThreshold attribute
        """
        return self._overCurrentThreshold

    @overCurrentThreshold.write  # type: ignore[no-redef]
    def overCurrentThreshold(self: MccsAPIU, value: float) -> None:
        """
        Set the overCurrentThreshold attribute.

        :param value: new value for the overCurrentThreshold attribute
        """
        self._overCurrentThreshold = value

    @attribute(dtype="DevDouble", label="Over Voltage threshold", unit="Volt")
    def overVoltageThreshold(self: MccsAPIU) -> float:
        """
        Return the overVoltageThreshold attribute.

        :return: the value of the overVoltageThreshold attribute
        """
        return self._overVoltageThreshold

    @overVoltageThreshold.write  # type: ignore[no-redef]
    def overVoltageThreshold(self: MccsAPIU, value: float) -> None:
        """
        Set the overVoltageThreshold attribute.

        :param value: new value for the overVoltageThreshold attribute
        """
        self._overVoltageThreshold = value

    @attribute(dtype="DevDouble", label="Humidity threshold", unit="percent")
    def humidityThreshold(self: MccsAPIU) -> float:
        """
        Return the humidity threshold.

        :return: the value of the humidityThreshold attribute
        """
        return self._humidityThreshold

    @humidityThreshold.write  # type: ignore[no-redef]
    def humidityThreshold(self: MccsAPIU, value: float) -> None:
        """
        Set the humidityThreshold attribute.

        :param value: new value for the humidityThreshold attribute
        """
        self._humidityThreshold = value

    # --------
    # Commands
    # --------

    class IsAntennaOnCommand(FastCommand):
        """A class for the MccsAPIU's IsAntennaOn() command."""

        def __init__(
            self: MccsAPIU.IsAntennaOnCommand,
            component_manager,
            logger: Optional[logging.Logger] = None,
        ) -> None:
            """
            Initialise a new instance.

            :param component_manager: the device to which this command belongs.
            :param logger: a logger for this command to use.
            """
            self._component_manager = component_manager
            super().__init__(logger)

        def do(self: MccsAPIU.IsAntennaOnCommand) -> bool:  # type: ignore[override]
            """
            Stateless hook for device IsAntennaOn() command.

            :return: True if the antenna is on.
            """
            return self._component_manager.is_antenna_on(argin)

    @command(dtype_in="DevULong", dtype_out=bool)
    def IsAntennaOn(self: MccsAPIU, argin: int) -> bool:  # type: ignore[override]
        """
        Power up the antenna.

        :param argin: the logical antenna id of the antenna to power
            up

        :return: whether the specified antenna is on or not
        """
        handler = self.get_command_object("IsAntennaOn")
        return handler(argin)

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    @command(dtype_in="DevULong", dtype_out="DevVarLongStringArray")
    def PowerUpAntenna(self: MccsAPIU, argin: int) -> DevVarLongStringArrayType:
        """
        Power up the antenna.

        :param argin: the logical antenna id of the antenna to power
            up

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpAntenna")
        result_code, unique_id = handler(argin)
        return ([result_code], [unique_id])

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    def PowerDownAntenna(self: MccsAPIU, argin: int) -> DevVarLongStringArrayType:
        """
        Power down the antenna.

        :param argin: the logical antenna id of the antenna to power
            down

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownAntenna")
        result_code, unique_id = handler(argin)
        return ([result_code], [unique_id])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def PowerUp(self: MccsAPIU) -> DevVarLongStringArrayType:
        """
        Power up.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUp")
        result_code, unique_id = handler()
        return ([result_code], [unique_id])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def PowerDown(self: MccsAPIU) -> DevVarLongStringArrayType:
        """
        Power down.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDown")
        result_code, unique_id = handler()
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
    return MccsAPIU.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
