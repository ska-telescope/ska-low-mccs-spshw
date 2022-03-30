# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a subrack Tango device for MCCS."""

from __future__ import annotations  # allow forward references in type hints

import json
import logging
import threading
from typing import Any, List, Optional, Tuple

import tango
from ska_tango_base.base import SKABaseDevice
from ska_tango_base.commands import (
    DeviceInitCommand,
    FastCommand,
    ResultCode,
    SubmittedSlowCommand,
)
from ska_tango_base.control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    SimulationMode,
    TestMode,
)
from tango.server import attribute, command, device_property

from ska_low_mccs.subrack import (
    SubrackComponentManager,
    SubrackData,
    SubrackHealthModel,
)

__all__ = ["MccsSubrack", "main"]


DevVarLongStringArrayType = Tuple[List[ResultCode], List[Optional[str]]]

class MccsSubrack(SKABaseDevice):
    """
    An implementation of MCCS Subrack device.

    The device is controlled by a remote microcontroller, which answers
    to simple commands. It has the capabilities to switch on and off
    individual TPMs, to measure temperatures, voltages and currents, and
    to set-check fan speeds.
    """

    # -----------------
    # Device Properties
    # -----------------
    SubrackIp = device_property(dtype=str, default_value="0.0.0.0")
    SubrackPort = device_property(dtype=int, default_value=8081)
    TileFQDNs = device_property(dtype=(str,), default_value=[])

    # ---------------
    # Initialisation
    # ---------------
    def init_device(self: MccsSubrack) -> None:
        """
        Initialise the device.

        This is overridden here to change the Tango serialisation model.
        """
        util = tango.Util.instance()
        util.set_serial_model(tango.SerialModel.NO_SYNC)
        self._max_workers = 1
        self._power_state_lock = threading.RLock()
        super().init_device()

    def _init_state_model(self: MccsSubrack) -> None:
        super()._init_state_model()
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubrackHealthModel(self.component_state_changed_callback)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsSubrack,
    ) -> SubrackComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        # InitCommand.do() would do this too late
        self._tpm_power_modes_lock = threading.Lock()
        self._tpm_power_modes = [PowerState.UNKNOWN] * SubrackData.TPM_BAY_COUNT

        return SubrackComponentManager(
            SimulationMode.TRUE,
            self.logger,
            self._max_workers,
            self.SubrackIp,
            self.SubrackPort,
            self._component_communication_status_changed,
            self.component_state_changed_callback,
        )

    def init_command_objects(self: MccsSubrack) -> None:
        """Initialise the command handlers for commands supported by this device."""
        super().init_command_objects()

        for (command_name, method_name) in [
            ("PowerOnTpm", 'turn_on_tpm'),
            ("PowerOffTpm", 'turn_off_tpm'),
            ("PowerUpTpms", 'turn_on_tpms'),
            ("PowerDownTpms", 'turn_off_tpms'),
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
        for (command_name, command_object) in [
            ("SetSubrackFanSpeed", self.SetSubrackFanSpeedCommand),
            ("SetSubrackFanMode", self.SetSubrackFanModeCommand),
            ("SetPowerSupplyFanSpeed", self.SetPowerSupplyFanSpeedCommand),
        ]:
            self.register_command_object(
                command_name,
                command_object(
                    self.component_manager, self.logger
                ),
            )

    class InitCommand(DeviceInitCommand):
        """Class that implements device initialisation for the MCCS Subrack device."""

        def do(  # type: ignore[override]
            self: MccsSubrack.InitCommand,
        ) -> tuple[ResultCode, str]:
            """
            Initialise the attributes and properties of the MccsSubrack.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """

            for tpm_number in range(1, SubrackData.TPM_BAY_COUNT + 1):
                self._device.set_change_event(f"tpm{tpm_number}PowerState", True, False)

            return (ResultCode.OK, "Init command completed OK")

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsSubrack,
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
        power_map = {
            PowerState.UNKNOWN: "component_unknown",
            PowerState.STANDBY: "component_standby",
            PowerState.OFF: "component_off",
            PowerState.ON: "component_on",
        }
        self.logger.debug(
            "Component communication status changed to " + str(communication_status)
        )

        action = action_map[communication_status]
        if action is not None:
            self.op_state_model.perform_action(action)
        else:
            power_supply_status = (
                self.component_manager._power_supply_component_manager.supplied_power_mode
            )
            if (
                self.admin_mode_model.admin_mode
                in [
                    AdminMode.ONLINE,
                    AdminMode.MAINTENANCE,
                ]
                and power_supply_status is not None
            ):
                action = power_map[power_supply_status]
                self.logger.debug(
                    "Switch component according to power supply status"
                    + str(power_supply_status)
                )
                self.op_state_model.perform_action(action)
            else:
                self.op_state_model.perform_action("component_unknown")
                self.logger.debug("Power supply status unknown")

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )
        power_status = self.component_manager.power_mode
        self.logger.debug(
            f"Power mode: {power_status}, Communicating: {self._health_model._communicating}"
        )
        if (power_status == PowerState.ON) and self._health_model._communicating:
            self.logger.debug("Checking tpm power modes")
            self.component_manager.check_tpm_power_modes()

    def component_state_changed_callback(
        self: MccsSubrack, state_change: dict[str, Any]
    ) -> None:
        """
        Handle change in the state of the component.

        This is a callback hook, called by the component manager when
        the state of the component changes.

        :param state_change: dictionary of state change parameters.
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

        self.logger.debug(
            "TPM power modes changed: old"
            + str(self._tpm_power_modes)
            + "new: "
            + str(tpm_power_modes)
        )

        with self._tpm_power_modes_lock:
            if "tpm_power_modes" in state_change.keys():
                tpm_power_modes = state_change.get("tpm_power_modes")
                for i in range(SubrackData.TPM_BAY_COUNT):
                    if self._tpm_power_modes[i] != tpm_power_modes[i]:
                        self._tpm_power_modes[i] = tpm_power_modes[i]
                        self.push_change_event(f"tpm{i+1}PowerState", tpm_power_modes[i])

    # ----------
    # Attributes
    # ----------
    @attribute(
        dtype=SimulationMode,
        memorized=True,
        hw_memorized=True,
    )
    def simulationMode(self: MccsSubrack) -> SimulationMode:
        """
        Report the simulation mode of the device.

        :return: Return the current simulation mode
        """
        return self.component_manager.simulation_mode

    @simulationMode.write  # type: ignore[no-redef]
    def simulationMode(self: MccsSubrack, value: int) -> None:
        """
        Set the simulation mode.

        :param value: The simulation mode, as a SimulationMode value
        """
        self.component_manager.simulation_mode = value

    @attribute(
        dtype=TestMode,
        memorized=True,
        hw_memorized=True,
    )
    def testMode(self: MccsSubrack) -> TestMode:
        """
        Report the test mode of the device.

        :return: the current test mode
        """
        return self.component_manager.test_mode

    @testMode.write  # type: ignore[no-redef]
    def testMode(self: MccsSubrack, value: TestMode) -> None:
        """
        Set the test mode.

        :param value: The test mode, as a TestMode value
        """
        self.component_manager.test_mode = TestMode(value)

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Backplane temperatures",
        unit="Celsius",
    )
    def backplaneTemperatures(self: MccsSubrack) -> tuple[float]:
        """
        Return the temperatures of the subrack backplane.

        Two values are returned, respectively for the first (bays 1-4)
        and second (bays 5-8) halves of the backplane.

        :return: the temperatures of the subrack backplane
        """
        return self.component_manager.backplane_temperatures

    @attribute(
        dtype=("DevFloat",),
        max_dim_x=2,
        label="Subrack board temperatures",
        unit="Celsius",
    )
    def boardTemperatures(self: MccsSubrack) -> tuple[float]:
        """
        Return the temperatures of the subrack management board.

        Two values are returned.

        :return: the temperatures of the subrack management board
        """
        return self.component_manager.board_temperatures

    @attribute(dtype="float", label="Board current")
    def boardCurrent(self: MccsSubrack) -> float:
        """
        Return the subrack management board current.

        Total current provided by the two power supplies.

        :return: the subrack management board current
        """
        return self.component_manager.board_current

    @attribute(dtype=("DevFloat",), max_dim_x=4, label="Subrack fans speeds (RPM)")
    def subrackFanSpeeds(self: MccsSubrack) -> tuple[float]:
        """
        Return the subrack fan speeds, in RPM.

        Four fans are present in the subrack back side.

        :return: the subrack fan speeds
        """
        return self.component_manager.subrack_fan_speeds

    @attribute(dtype=("DevFloat",), max_dim_x=4, label="Subrack fans speeds (%)")
    def subrackFanSpeedsPercent(self: MccsSubrack) -> tuple[float]:
        """
        Return the subrack fan speeds in percent.

        This is the commanded value, the
        relation between this level and the actual RPMs is not linear. Subrack speed is
        managed automatically by the controller, by default (see subrack_fan_modes)
        Commanded speed is the same for fans 1-2 and 3-4.

        :return: the subrack fan speeds in percent
        """
        return self.component_manager.subrack_fan_speeds_percent

    @attribute(dtype=("DevUShort",), max_dim_x=4, label="Subrack Fan Mode")
    def subrackFanMode(self: MccsSubrack) -> list[int]:
        """
        Return the subrackFanMode.

        The mode is 1 (AUTO) at power-on When mode is AUTO,
        the fan speed is managed automatically. When mode is MANUAL (0), the fan speed
        is directly controlled using the SetSubrackFanSpeed command Mode is the same for
        fans 1-2 and 3-4.

        :return: the subrack fan mode, 1 AUTO 0 MANUAL
        """
        return self.component_manager.subrack_fan_modes

    @attribute(dtype=("DevBoolean",), max_dim_x=8, label="TPM present")
    def tpmPresent(self: MccsSubrack) -> tuple[bool]:
        """
        Return info about TPM board present on subrack.

        Returns a list of 8 Bool
        specifying presence of TPM in bays 1-8.

        :return: the TPMs detected
        """
        return self.component_manager.tpm_present

    @attribute(dtype=("DevUShort",), max_dim_x=8, label="TPM Supply Fault")
    def tpmSupplyFault(self: MccsSubrack) -> tuple[int]:
        """
        Return info about about TPM supply fault status.

        Returns a list of 8 int
        specifying fault codeof TPM in bays 1-8 Current codes are 0 (no fault) or 1
        (fault)

        :return: the TPM supply fault status
        """
        return self.component_manager.tpm_supply_fault

    @attribute(dtype=(float,), label="TPM temperatures", max_dim_x=8)
    def tpmTemperatures(self: MccsSubrack) -> tuple[float]:
        """
        Return the temperatures of the TPMs housed in subrack bays.

        Command is not yet implemented.

        :return: the TPM temperatures
        """
        return self.component_manager.tpm_temperatures

    @attribute(dtype=("DevFloat",), max_dim_x=8, label="TPM power")
    def tpmPowers(self: MccsSubrack) -> tuple[float]:
        """
        Return the power used by TPMs in the subrack bays.

        :return: the TPM powers
        """
        return self.component_manager.tpm_powers

    @attribute(dtype=("DevFloat",), max_dim_x=8, label="TPM voltage")
    def tpmVoltages(self: MccsSubrack) -> tuple[float]:
        """
        Return the voltage at the power connector.

        In the subrack bays Voltage is (approx) 0 for powered off bays.

        :return: the TPM voltages
        """
        return self.component_manager.tpm_voltages

    @attribute(dtype=("DevFloat",), max_dim_x=8, label="TPM currents")
    def tpmCurrents(self: MccsSubrack) -> tuple[float]:
        """
        Return the currents of the subrack bays.

        (hence the currents of the TPMs housed in those bays).

        :return: the TPM currents
        """
        return self.component_manager.tpm_currents

    @attribute(dtype=int, label="TPM count")
    def tpmCount(self: MccsSubrack) -> int:
        """
        Return the number of TPMs connected to this subrack.

        :return: the number of TPMs connected to this subrack
        """
        return self.component_manager.tpm_count

    @attribute(
        dtype=PowerState,
        label="TPM bay 1 power mode",
    )
    def tpm1PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 1.

        :return: the power mode of TPM bay 1.
        """
        return self._tpm_power_modes[0]

    @attribute(
        dtype=PowerState,
        label="TPM bay 2 power mode",
    )
    def tpm2PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 2.

        :return: the power mode of TPM bay 2.
        """
        return self._tpm_power_modes[1]

    @attribute(
        dtype=PowerState,
        label="TPM bay 3 power mode",
    )
    def tpm3PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 3.

        :return: the power mode of TPM bay 3.
        """
        return self._tpm_power_modes[2]

    @attribute(
        dtype=PowerState,
        label="TPM bay 4 power mode",
    )
    def tpm4PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 4.

        :return: the power mode of TPM bay 4.
        """
        return self._tpm_power_modes[3]

    @attribute(
        dtype=PowerState,
        label="TPM bay 5 power mode",
    )
    def tpm5PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 5.

        :return: the power mode of TPM bay 5.
        """
        return self._tpm_power_modes[4]

    @attribute(
        dtype=PowerState,
        label="TPM bay 6 power mode",
    )
    def tpm6PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 6.

        :return: the power mode of TPM bay 6.
        """
        return self._tpm_power_modes[5]

    @attribute(
        dtype=PowerState,
        label="TPM bay 7 power mode",
    )
    def tpm7PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 7.

        :return: the power mode of TPM bay 7.
        """
        return self._tpm_power_modes[6]

    @attribute(
        dtype=PowerState,
        label="TPM bay 8 power mode",
    )
    def tpm8PowerState(self: MccsSubrack) -> PowerState:
        """
        Return the power mode of TPM bay 8.

        :return: the power mode of TPM bay 8.
        """
        return self._tpm_power_modes[7]

    @attribute(dtype=("DevFloat",), max_dim_x=3, label="power supply fan speed")
    def powerSupplyFanSpeeds(self: MccsSubrack) -> tuple[float]:
        """
        Return the powerSupply FanSpeed for the two redundant power supplies.

        Values expressed in percent of maximum.

        :return: the power supply fan speeds
        """
        return self.component_manager.power_supply_fan_speeds

    @attribute(dtype=("DevFloat",), max_dim_x=2, label="power_supply current")
    def powerSupplyCurrents(self: MccsSubrack) -> tuple[float]:
        """
        Return the power supply currents.

        :return: the power supply currents for the two redundant power supplies
        """
        return self.component_manager.power_supply_currents

    @attribute(dtype=("DevFloat",), max_dim_x=2, label="power_supply Powers")
    def powerSupplyPowers(self: MccsSubrack) -> tuple[float]:
        """
        Return the power supply power for the two redundant power supplies.

        :return: the power supply power
        """
        return self.component_manager.power_supply_powers

    @attribute(dtype=("DevFloat",), max_dim_x=2, label="power_supply voltage")
    def powerSupplyVoltages(self: MccsSubrack) -> tuple[float]:
        """
        Return the power supply voltages for the two redundant power supplies.

        :return: the power supply voltages
        """
        return self.component_manager.power_supply_voltages

    # --------
    # Commands
    # --------

    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    def PowerOnTpm(self: MccsSubrack, argin: int) -> DevVarLongStringArrayType:
        """
        Power up the TPM.

        Power on an individual TPM, specified by the TPM ID (range
        1-8) Execution time is ~1.5 seconds.

        :param argin: the logical id of the TPM to power
            up

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOnTpm")
        unique_id, return_code = self.component_manager.enqueue(handler, argin)
        return ([return_code], [unique_id])


    @command(
        dtype_in="DevULong",
        dtype_out="DevVarLongStringArray",
    )
    def PowerOffTpm(self: MccsSubrack, argin: int) -> DevVarLongStringArrayType:
        """
        Power down the TPM.

        Power off an individual TPM, specified by the TPM ID (range
        1-8) Execution time is ~1.5 seconds.

        :param argin: the logical id of the TPM to power
            down

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerOffTpm")
        unique_id, return_code = self.component_manager.enqueue(handler, argin)
        return ([return_code], [unique_id])

    @command(
        dtype_out="DevVarLongStringArray",
    )
    def PowerUpTpms(self: MccsSubrack) -> DevVarLongStringArrayType:
        """
        Power up the TPMs.

        Power on all the TPMs in the subrack. Execution time depends
        on the number of TPMs present, for a fully populated subrack it may exceed 10
        seconds.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerUpTpms")
        unique_id, return_code = self.component_manager.enqueue(handler)
        return ([return_code], [unique_id])


    @command(dtype_out="DevVarLongStringArray")
    def PowerDownTpms(self: MccsSubrack) -> DevVarLongStringArrayType:
        """
        Power down all the TPMs.

        Power off all the TPMs in the subrack. Execution time
        depends on the number of TPMs present, for a fully populated subrack it may
        exceed 10 seconds.

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("PowerDownTpms")
        unique_id, return_code = self.component_manager.enqueue(handler)
        return ([return_code], [unique_id])

    class SetSubrackFanSpeedCommand(FastCommand):
        """
        Class for handling the SetSubrackFanSpeed() command.

        This command set the backplane fan speed.
        """
        def __init__(
            self: MccsSubrack.SetSubrackFanSpeedCommand,
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

        def do(  # type: ignore[override]
            self: MccsSubrack.SetSubrackFanSpeedCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:'.MccsSubrack.SetSubrackFanSpeed' command.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string message
                indicating status. The message is for information purpose only.

            :raises ValueError: if the JSON input lacks mandatory parameters
            """

            params = json.loads(argin)
            fan_id = params.get("FanID", None)
            speed_percent = params.get("SpeedPWN%", None)
            if fan_id or speed_percent is None:
                self._component_manager.logger.error(
                    "fan_ID and fan speed are mandatory parameters"
                )
                raise ValueError("fan_ID and fan speed are mandatory parameters")

            return self._component_manager.set_subrack_fan_speed(fan_id, speed_percent)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetSubrackFanSpeed(self: MccsSubrack, argin: str) -> DevVarLongStringArrayType:
        """
        Set the subrack backplane fan speed.

        :param argin: json dictionary with mandatory keywords:

        * fan_id - (int) id of the selected fan accepted value: 1-4
        * speed_percent - (float) percentage value of fan RPM  (MIN 0=0% - MAX
                100=100%)

        Setting fan speed for one of fans in groups (1-2) and (3-4) sets
        the speed for both fans in that group

        :return: A tuple containing return code and string message indicating
                status. The message is for information purpose only.
        """
        handler = self.get_command_object("SetSubrackFanSpeed")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    class SetSubrackFanModeCommand(FastCommand):
        """
        Class for handling the SetSubrackFanMode() command.

        This command can set the selected fan to manual or auto mode.
        """
        def __init__(
            self: MccsSubrack.SetSubrackFanModeCommand,
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

        def do(  # type: ignore[override]
            self: MccsSubrack.SetSubrackFanModeCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsSubrack.SetSubrackFanMode` command.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.

            :raises ValueError: if the JSON input lacks of mandatory parameters
            """
            params = json.loads(argin)
            fan_id = params.get("fan_id", None)
            mode = params.get("mode", None)
            if fan_id or mode is None:
                self._component_manager.logger.error(
                    "Fan_id and mode are mandatory parameters"
                )
                raise ValueError("Fan_id and mode are mandatory parameter")
       
            return self._component_manager.set_subrack_fan_modes(fan_id, mode)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetSubrackFanMode(self: MccsSubrack, argin: str) -> DevVarLongStringArrayType:
        """
        Set Fan Operational Mode: 1 AUTO, 0 MANUAL.

        :param argin: json dictionary with mandatory keywords:

        * fan_id - (int) id of the selected fan accepted value: 1-4
        * mode - (int) 1 AUTO, 0 MANUAL

        Setting fan speed for one of fans in groups (1-2) and (3-4) sets
        the speed for both fans in that group

        :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
        """
        handler = self.get_command_object("SetSubrackFanMode")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])

    class SetPowerSupplyFanSpeedCommand(FastCommand):
        """
        Class for handling the SetPowerSupplyFanSpeed command.

        This command set the selected power supply fan speed.
        """

        def __init__(
            self: MccsSubrack.SetPowerSupplyFanSpeedCommand,
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

        def do(  # type: ignore[override]
            self: MccsSubrack.SetPowerSupplyFanSpeedCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Implement :py:meth:`.MccsSubrack.SetPowerSupplyFanSpeed` command.

            :param argin: a JSON-encoded dictionary of arguments

            :return: A tuple containing a return code and a string
                    message indicating status. The message is for
                    information purpose only.

            :raises ValueError: if the JSON input lacks of mandatory parameters
            """
        
            params = json.loads(argin)
            power_supply_fan_id = params.get("power_supply_fan_id", None)
            speed_percent = params.get("speed_%", None)
            if power_supply_fan_id or speed_percent is None:
                self._component_manager.logger.error(
                    "power_supply_fan_id and speed_percent are mandatory " "parameters"
                )
                raise ValueError(
                    "power_supply_fan_id and speed_percent are mandatory " "parameters"
                )

            return self._component_manager.set_power_supply_fan_speed(
                power_supply_fan_id, speed_percent)

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def SetPowerSupplyFanSpeed(
        self: MccsSubrack, argin: str
    ) -> DevVarLongStringArrayType:
        """
        Set the selected power supply fan speed.

        :param argin: json dictionary with mandatory keywords:

        * power_supply_id - (int) power supply id from 1 to 2
        * speed_percent - (float) fanspeed in percent

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("SetPowerSupplyFanSpeed")
        (return_code, unique_id) = handler(argin)
        return ([return_code], [unique_id])


# ----------
# Run server
# ----------


def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsSubrack.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
