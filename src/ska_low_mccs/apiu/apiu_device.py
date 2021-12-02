# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements the MCCS APIU device."""

from __future__ import annotations  # allow forward references in type hints

from typing import List, Optional, Tuple

import tango
from tango.server import attribute, command, device_property

from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import BaseCommand, ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState, PowerMode, SimulationMode

from ska_low_mccs.apiu import ApiuComponentManager, ApiuHealthModel
from ska_low_mccs.component import CommunicationStatus


__all__ = ["MccsAPIU", "main"]

DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]


def create_return(success: Optional[bool], action: str) -> tuple[ResultCode, str]:
    """
    Create a tuple with ResultCode and string message.

    Helper function to package up a boolean result into a
    (:py:class:`~ska_tango_base.commands.ResultCode`, message) tuple.

    :param success: whether execution of the action was successful. This
        may be None, in which case the action was not performed due to
        redundancy (i.e. it was already done).
    :param action: Informal description of the action that the command
        performs, for use in constructing a message

    :return: A tuple containing a return code and a string
        message indicating status. The message is for
        information purpose only.
    """
    if success is None:
        return (ResultCode.OK, f"APIU {action} is redundant")
    elif success in [True, ResultCode.OK]:
        return (ResultCode.OK, f"APIU {action} successful")
    else:
        return (ResultCode.FAILED, f"APIU {action} failed")


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
        super().init_device()

    def _init_state_model(self: MccsAPIU) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = ApiuHealthModel(self.health_changed)
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
            self._component_communication_status_changed,
            self._component_power_mode_changed,
            self._component_fault,
            self._message_queue_size_changed,
            self.are_antennas_on_changed,
        )

    def init_command_objects(self: MccsAPIU) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, command_object) in [
            ("IsAntennaOn", self.IsAntennaOnCommand),
            ("PowerUpAntenna", self.PowerUpAntennaCommand),
            ("PowerDownAntenna", self.PowerDownAntennaCommand),
            ("PowerUp", self.PowerUpCommand),
            ("PowerDown", self.PowerDownCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(
                    self.component_manager, self.op_state_model, self.logger
                ),
            )

    class InitCommand(SKABaseDevice.InitCommand):
        """Class that implements device initialisation for the MCCS APIU device."""

        def do(self: MccsAPIU.InitCommand) -> tuple[ResultCode, str]:  # type: ignore[override]
            """
            Initialise the attributes and properties of the :py:class:`.MccsAPIU`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            super().do()

            device = self.target

            device._are_antennas_on = None
            device.set_change_event("areAntennasOn", True, False)

            device._isAlive = True
            device._overCurrentThreshold = 0.0
            device._overVoltageThreshold = 0.0
            device._humidityThreshold = 0.0

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

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

    def _component_power_mode_changed(
        self: MccsAPIU,
        power_mode: PowerMode,
    ) -> None:
        """
        Handle change in the power mode of the component.

        This is a callback hook, called by the component manager when
        the power mode of the component changes. It is implemented here
        to drive the op_state.

        :param power_mode: the power mode of the component.
        """
        action_map = {
            PowerMode.OFF: "component_off",
            PowerMode.STANDBY: "component_standby",
            PowerMode.ON: "component_on",
            PowerMode.UNKNOWN: "component_unknown",
        }

        self.op_state_model.perform_action(action_map[power_mode])

    def _component_fault(
        self: MccsAPIU,
        is_fault: bool,
    ) -> None:
        """
        Handle change in the fault status of the component.

        This is a callback hook, called by the component manager when
        the component fault status changes. It is implemented here to
        drive the op_state.

        :param is_fault: whether the component is faulting or not.
        """
        if is_fault:
            self.op_state_model.perform_action("component_fault")
            self._health_model.component_fault(True)
        else:
            self._component_power_mode_changed(self.component_manager.power_mode)
            self._health_model.component_fault(False)

    def _message_queue_size_changed(
        self: MccsAPIU,
        size: int,
    ) -> None:
        """
        Handle change in component manager message queue size.

        :param size: the new size of the component manager's message
            queue
        """
        # TODO: This should push an event but the details have to wait for SP-1827
        self.logger.info(f"Message queue size is now {size}")

    def health_changed(self: MccsAPIU, health: HealthState) -> None:
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

    def are_antennas_on_changed(self: MccsAPIU, are_antennas_on: list[bool]) -> None:
        """
        Handle power changes to the antennas.

        Responsible for updating the tango side of things i.e. making sure the
        attribute is up to date and events are pushed.

        :param are_antennas_on: whether each antenna is powered
        """
        self._are_antennas_on: list[bool]
        if self._are_antennas_on == are_antennas_on:
            return
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
    class IsAntennaOnCommand(BaseCommand):
        """The command class for the IsAntennaOn command."""

        def do(self: MccsAPIU.IsAntennaOnCommand, argin: int) -> bool:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsAPIU.IsAntennaOn` command functionality.

            :param argin: the logical antenna id of the antenna to power
                up

            :return: whether the specified antenna is on or not
            """
            component_manager = self.target
            return component_manager.is_antenna_on(argin)

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

    class PowerUpAntennaCommand(ResponseCommand):
        """The command class for the PowerDownAntenna command."""

        def do(  # type: ignore[override]
            self: MccsAPIU.PowerUpAntennaCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsAPIU.PowerUpAntenna` command functionality.

            :param argin: the logical antenna id of the antenna to power
                up

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_on_antenna(argin)
            return create_return(success, f"antenna {argin} power-up")

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
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class PowerDownAntennaCommand(ResponseCommand):
        """The command class for the PowerDownAntenna command."""

        def do(  # type: ignore[override]
            self: MccsAPIU.PowerDownAntennaCommand, argin: int
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsAPIU.PowerDownAntenna` command functionality.

            :param argin: the logical antenna id of the antenna to power
                down

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_off_antenna(argin)
            return create_return(success, f"antenna {argin} power-down")

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
        (return_code, message) = handler(argin)
        return ([return_code], [message])

    class PowerUpCommand(ResponseCommand):
        """
        Class for handling the PowerUp() command.

        The PowerUp command turns on all of the antennas that are
        powered by this APIU.
        """

        def do(self: MccsAPIU.PowerUpCommand) -> tuple[ResultCode, str]:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsAPIU.PowerUp` command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_on_antennas()
            return create_return(success, "power-up")

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
        (return_code, message) = handler()
        return ([return_code], [message])

    class PowerDownCommand(ResponseCommand):
        """
        Class for handling the PowerDown() command.

        The PowerDown command turns on all of the antennas that are
        powered by this APIU.
        """

        def do(self: MccsAPIU.PowerDownCommand) -> tuple[ResultCode, str]:  # type: ignore[override]
            """
            Implement :py:meth:`.MccsAPIU.PowerDown` command functionality.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            success = component_manager.turn_off_antennas()
            return create_return(success, "power-down")

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
        (return_code, message) = handler()
        return ([return_code], [message])


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
