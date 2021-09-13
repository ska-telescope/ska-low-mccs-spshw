# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
An implementation of a subrack management board driver.

Some assumptions of this class are:

* The subrack management board supplies power to various modules, such
  as TPMs. The subrack can deny or supply power to these modules; i.e.
  turn them off and on. If a module supports a low-power standby mode,
  then you have to talk to the module itself in order to switch it
  between standby and on.
* The subrack management board has its own sensors for its temperature,
  current, etc. But it cannot measure parameters
  of a TPM even when the TPM is turned off

These assumptions may need to change in future.
"""
from __future__ import annotations  # allow forward references in type hints

import time
import logging
from typing import Callable, cast, List, Optional

from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import (
    ControlMode,
    CommunicationStatus,
    MessageQueue,
    MessageQueueComponentManager,
    WebHardwareClient,
)

__all__ = ["SubrackDriver"]


class SubrackDriver(MessageQueueComponentManager):
    """
    A driver for a subrack management board.

    :todo: for now we assume that the subrack management board can turn
        itself off and on. Actually, this would be done via the SPS
        cabinet. Once we have an SPS cabinet simulator, we should fix
        this.

    :todo: Remove all unnecessary variables and constants after
            all methods are completed and tested
    """

    DEFAULT_BACKPLANE_TEMPERATURES = [38.0, 39.0]
    DEFAULT_BOARD_TEMPERATURES = [39.0, 40.0]
    DEFAULT_BOARD_CURRENT = 1.1
    DEFAULT_SUBRACK_FAN_SPEED = [4999.0, 5000.0, 5001.0, 5002.0]
    MAX_SUBRACK_FAN_SPEED = 8000.0
    DEFAULT_SUBRACK_FAN_MODES = [ControlMode.AUTO] * 4
    DEFAULT_TPM_POWER_MODES = [PowerMode.OFF] * 8
    DEFAULT_TPM_PRESENT = [True] * 8
    DEFAULT_POWER_SUPPLY_POWERS = [50.0, 70.0]
    DEFAULT_POWER_SUPPLY_VOLTAGES = [12.0, 12.1]
    DEFAULT_POWER_SUPPLY_CURRENTS = [50.0 / 12.0, 70.0 / 12.1]
    DEFAULT_POWER_SUPPLY_FAN_SPEED = [90.0, 100.0]
    DEFAULT_TPM_COUNT = 8

    def __init__(
        self: SubrackDriver,
        message_queue: MessageQueue,
        logger: logging.Logger,
        ip: str,
        port: int,
        communication_status_changed_callback: Callable[[CommunicationStatus], None],
        component_fault_callback: Callable[[bool], None],
        component_tpm_power_changed_callback: Optional[
            Callable[[Optional[list[bool]]], None]
        ],
        tpm_present: Optional[list[bool]] = None,
    ) -> None:
        """
        Initialise a new instance and tries to connect to the given IP and port.

        :param message_queue: the message queue to be used by this
            driver
        :param logger: a logger for this driver to use
        :param ip: IP address for hardware tile
        :param port: IP address for hardware control
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param component_fault_callback: callback to be called when the
            component faults (or stops faulting)
        :param component_tpm_power_changed_callback: callback to be
            called when the power mode of one of the TPMs in the subrack
            changes
        :param tpm_present: List of TPMs which are expected to be
            present in the subrack. Usually from Tango database.
        """
        self.logger = logger
        self._ip = ip
        self._port = port

        self._backplane_temperatures = self.DEFAULT_BACKPLANE_TEMPERATURES
        self._board_temperatures = self.DEFAULT_BOARD_TEMPERATURES
        self._board_current = self.DEFAULT_BOARD_CURRENT
        self._subrack_fan_speeds = self.DEFAULT_SUBRACK_FAN_SPEED
        self._subrack_fan_modes = self.DEFAULT_SUBRACK_FAN_MODES
        self._power_supply_currents = self.DEFAULT_POWER_SUPPLY_CURRENTS
        self._power_supply_voltages = self.DEFAULT_POWER_SUPPLY_VOLTAGES
        self._power_supply_fan_speeds = self.DEFAULT_POWER_SUPPLY_FAN_SPEED
        if tpm_present is None:
            self._tpm_present = self.DEFAULT_TPM_PRESENT
        else:
            self._tpm_present = tpm_present
        self._are_tpms_on = self.DEFAULT_TPM_POWER_MODES
        self._tpm_count = self.DEFAULT_TPM_COUNT
        self._bay_count = self.DEFAULT_TPM_COUNT

        self._client = WebHardwareClient(self._ip, self._port)

        self._component_tpm_power_changed_callback = (
            component_tpm_power_changed_callback
        )

        super().__init__(
            message_queue,
            logger,
            communication_status_changed_callback,
            None,
            component_fault_callback,
        )

    def start_communicating(self: SubrackDriver) -> None:
        """Establish communication with the subrack."""
        super().start_communicating()
        self.enqueue(self._connect_to_subrack)

    def _connect_to_subrack(self: SubrackDriver) -> None:
        connected = self._client.connect()
        if connected:
            self.update_communication_status(CommunicationStatus.ESTABLISHED)
        else:
            self.logger.error("status:ERROR")
            self.logger.info("info: Not connected")

    def stop_communicating(self: SubrackDriver) -> None:
        """Stop communicating with the subrack."""
        super().stop_communicating()
        self._client.disconnect()

    def _tpm_power_changed(self: SubrackDriver) -> None:
        """
        Handle a change in TPM power.

        This is a helper method that calls the callback if it exists.
        """
        if self._component_tpm_power_changed_callback is not None:
            self._component_tpm_power_changed_callback(self.are_tpms_on())

    @property
    def backplane_temperatures(self: SubrackDriver) -> list[float]:
        """
        Return the subrack backplane temperatures.

        :return: the subrack backplane temperatures
        """
        self.logger.debug("Reading backplane temperature")

        response = self._client.get_attribute("backplane_temperatures")
        if response["status"] == "OK":
            self._backplane_temperatures = cast(List[float], response["value"])
        return self._backplane_temperatures

    @property
    def board_temperatures(self: SubrackDriver) -> list[float]:
        """
        Return the subrack management board temperatures.

        :return: the board temperatures, in degrees celsius
        """
        self.logger.debug("Reading board temperature")
        response = self._client.get_attribute("board_temperatures")
        if response["status"] == "OK":
            self._board_temperatures = cast(List[float], response["value"])
        return self._board_temperatures

    @property
    def board_current(self: SubrackDriver) -> float:
        """
        Return the subrack management board current.

        :return: the subrack management board current
        """
        self.logger.debug("Reading board current")
        response = self._client.get_attribute("board_current")
        if response["status"] == "OK":
            self._board_current = cast(float, response["value"])
        return self._board_current

    @property
    def subrack_fan_speeds(self: SubrackDriver) -> list[float]:
        """
        Return the subrack backplane fan speeds (in RPMs).

        :return: the subrack fan speeds (RPMs)
        """
        self.logger.debug("Reading backplane fan speed")
        response = self._client.get_attribute("subrack_fan_speeds")
        if response["status"] == "OK":
            self._subrack_fan_speeds = cast(List[float], response["value"])
        return self._subrack_fan_speeds

    @property
    def subrack_fan_speeds_percent(self: SubrackDriver) -> list[float]:
        """
        Return the subrack backplane fan speeds in percent.

        :return: the fan speed, in percent
        """
        self.logger.debug("Reading backplane fan speed percent")
        response = self._client.get_attribute("subrack_fan_speeds_percent")
        if response["status"] == "OK":
            self._subrack_fan_speeds_percent = cast(List[float], response["value"])
        return self._subrack_fan_speeds_percent

    @property
    def subrack_fan_modes(self: SubrackDriver) -> list[ControlMode]:
        """
        Return the subrack fan Mode.

        :return: subrack fan mode AUTO or  MANUAL
        """
        self.logger.debug("Reading backplane fan modes")
        response = self._client.get_attribute("subrack_fan_modes")
        if response["status"] == "OK":
            self._subrack_fan_modes = cast(List[ControlMode], response["value"])
        return self._subrack_fan_modes

    @property
    def tpm_count(self: SubrackDriver) -> int:
        """
        Return the number of TPMs housed in this subrack. If powered off return the last
        value stored, as it should not change often and is meaningless when powered off.

        :return: the number of TPMs housed in this subrack
        """
        self.logger.debug("Reading number of TPMs")
        response = self._client.get_attribute("tpm_present")
        if response["status"] == "OK":
            self._tpm_count = sum(cast(List[int], response["value"]))
        return self._tpm_count

    @property
    def bay_count(self: SubrackDriver) -> int:
        """
        Return the number of TPM bays housed in this subrack.

        :return: the number of TPM bays housed in this subrack
        """
        return self._bay_count

    def _check_tpm_id(self: SubrackDriver, logical_tpm_id: int) -> None:
        """
        Helper method to check that a TPM id passed as an argument is within range.

        :param logical_tpm_id: the id to check

        :raises ValueError: if the tpm id is out of range for this
            subrack
        """
        if logical_tpm_id < 1 or logical_tpm_id > self.bay_count:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; "
                f"this subrack has {self.tpm_count} boards."
            )
        if self._tpm_present[logical_tpm_id - 1] is False:
            raise ValueError(
                f"Cannot access TPM {logical_tpm_id}; " "TPM not present in this bay"
            )

    @property
    def tpm_temperatures(self: SubrackDriver) -> list[float]:
        """
        Return the temperatures of the TPMs housed in this subrack.

        :return: the temperatures of the TPMs housed in this subrack
        """
        self.logger.warning("SubrackDriver: tpm_temperatures is not implemented")
        return [0.0] * 8

    @property
    def tpm_currents(self: SubrackDriver) -> list[float]:
        """
        Return the currents of the TPMs housed in this subrack.

        :return: the currents of the TPMs housed in this subrack
        """
        response = self._client.get_attribute("tpm_currents")
        if response["status"] == "OK":
            self._tpm_currents = cast(List[float], response["value"])
        return self._tpm_currents

    @property
    def tpm_powers(self: SubrackDriver) -> list[float]:
        """
        Return the powers of the TPMs housed in this subrack.

        :return: the powers of the TPMs housed in this subrack
        """
        response = self._client.get_attribute("tpm_powers")
        if response["status"] == "OK":
            self._tpm_powers = cast(List[float], response["value"])
        return self._tpm_powers

    @property
    def tpm_voltages(self: SubrackDriver) -> list[float]:
        """
        Return the voltages of the TPMs housed in this subrack.

        :return: the voltages of the TPMs housed in this subrack
        """
        response = self._client.get_attribute("tpm_voltages")
        if response["status"] == "OK":
            self._tpm_voltages = cast(List[float], response["value"])
        return self._tpm_voltages

    @property
    def power_supply_fan_speeds(self: SubrackDriver) -> list[float]:
        """
        Return the power supply fan speeds for this subrack.

        :return: the power supply fan speed
        """
        response = self._client.get_attribute("power_supply_fan_speeds")
        if response["status"] == "OK":
            self._power_supply_fan_speeds = cast(List[float], response["value"])
        return self._power_supply_fan_speeds

    @property
    def power_supply_currents(self: SubrackDriver) -> list[float]:
        """
        Return the power supply currents for this subrack.

        :return: the power supply current
        """
        response = self._client.get_attribute("power_supply_currents")
        if response["status"] == "OK":
            self._power_supply_currents = cast(List[float], response["value"])
        return self._power_supply_currents

    @property
    def power_supply_powers(self: SubrackDriver) -> list[float]:
        """
        Return the power supply power for this subrack.

        :return: the power supply power
        """
        response = self._client.get_attribute("power_supply_powers")
        if response["status"] == "OK":
            self._power_supply_powers = cast(List[float], response["value"])
        return self._power_supply_powers

    @property
    def power_supply_voltages(self: SubrackDriver) -> list[float]:
        """
        Return the power supply voltages for this subrack.

        :return: the power supply voltages
        """
        response = self._client.get_attribute("power_supply_voltages")
        if response["status"] == "OK":
            self._power_supply_voltages = cast(List[float], response["value"])
        return self._power_supply_voltages

    @property
    def tpm_present(self: SubrackDriver) -> list[bool]:
        """
        Return the tpm detected in the subrack.

        :return: list of tpm detected
        """
        response = self._client.get_attribute("tpm_present")
        if response["status"] == "OK":
            self._tpm_present = cast(List[bool], response["value"])
        return self._tpm_present

    @property
    def tpm_supply_fault(self: SubrackDriver) -> list[int]:
        """
        Return info about about TPM supply fault status.

        :return: the TPM supply fault status
        """
        response = self._client.get_attribute("tpm_supply_fault")
        if response["status"] == "OK":
            self._tpm_supply_fault = cast(List[int], response["value"])
        return self._tpm_supply_fault

    def are_tpms_on(self: SubrackDriver) -> Optional[list[bool]]:
        """
        Returns whether each TPM is powered or not.

        Or None if the subrack itself is turned off.

        :return: whether each TPM is powered or not.
        """
        response = self._client.get_attribute("tpm_on_off")
        if response["status"] == "OK":
            self._are_tpms_on = cast(List[bool], response["value"])
        return self._are_tpms_on

    def is_tpm_on(self: SubrackDriver, logical_tpm_id: int) -> Optional[bool]:
        """
        Return whether a specified TPM is turned on.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be checked

        :return: whether the TPM is on, or None if the subrack itself
            is off
        """
        self._check_tpm_id(logical_tpm_id)
        return self._are_tpms_on[logical_tpm_id - 1]

    def turn_off_tpm(self: SubrackDriver, logical_tpm_id: int) -> bool:
        """
        Turn off a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned off

        :return: success value
        """
        self._check_tpm_id(logical_tpm_id)
        response = self._client.execute_command("turn_off_tpm", str(logical_tpm_id))
        self.logger.debug(
            "TpmDriver:" + response["command"] + ": " + response["status"]
        )
        timeout = 10
        while self._client.execute_command("command_completed")["retvalue"] is False:
            self.logger.debug("waiting...")
            time.sleep(1)
            timeout = timeout - 1
            if timeout <= 0:
                break
        if timeout > 0:
            self.logger.debug(response["command"] + ": completed")
            self._tpm_power_changed()
        else:
            self.logger.debug(response["command"] + ": timeout")
            response = self._client.execute_command("abort_command")
        return timeout > 0

    def turn_on_tpm(self: SubrackDriver, logical_tpm_id: int) -> bool:
        """
        Turn on a specified TPM.

        :param logical_tpm_id: this subrack's internal id for the
            TPM to be turned on

        :return: success status
        """
        self._check_tpm_id(logical_tpm_id)
        response = self._client.execute_command("turn_on_tpm", str(logical_tpm_id))
        self.logger.debug(
            "TpmDriver:" + response["command"] + ": " + response["status"]
        )
        timeout = 10
        while self._client.execute_command("command_completed")["retvalue"] is False:
            self.logger.debug("waiting...")
            time.sleep(1)
            timeout = timeout - 1
            if timeout <= 0:
                break
        if timeout > 0:
            self.logger.debug(response["command"] + ": completed")
            self._tpm_power_changed()
        else:
            self.logger.debug(response["command"] + ": timeout")
            response = self._client.execute_command("abort_command")
        return timeout > 0

    def turn_on_tpms(self: SubrackDriver) -> bool:
        """
        Turn on all TPMs.

        :return: success value
        """
        response = self._client.execute_command("turn_on_tpms")
        self.logger.debug(
            "TpmDriver:" + response["command"] + ": " + response["status"]
        )
        timeout = 20
        while self._client.execute_command("command_completed")["retvalue"] is False:
            self.logger.debug("waiting...")
            time.sleep(1)
            timeout = timeout - 1
            if timeout <= 0:
                break
        if timeout > 0:
            self.logger.debug(response["command"] + ": completed")
            self._tpm_power_changed()
        else:
            self.logger.debug(response["command"] + ": timeout")
            response = self._client.execute_command("abort_command")
        return timeout > 0

    def turn_off_tpms(self: SubrackDriver) -> bool:
        """
        Turn off all TPMs.

        :return: success value
        """
        response = self._client.execute_command("turn_off_tpms")
        self.logger.debug(
            "TpmDriver:" + response["command"] + ": " + response["status"]
        )
        timeout = 20
        while self._client.execute_command("command_completed")["retvalue"] is False:
            self.logger.debug("waiting...")
            time.sleep(1)
            timeout = timeout - 1
            if timeout <= 0:
                break
        if timeout > 0:
            self.logger.debug(response["command"] + ": completed")
            self._tpm_power_changed()
        else:
            self.logger.debug(response["command"] + ": timeout")
            response = self._client.execute_command("abort_command")
        return timeout > 0

    def set_subrack_fan_speed(
        self: SubrackDriver, fan_id: int, speed_percent: float
    ) -> bool:
        """
        Set the subrack backplane fan speed in percent.

        :param fan_id: id of the selected fan accepted value: 1-4
        :param speed_percent: percentage value of fan RPM  (MIN 0=0% - MAX 100=100%)

        :return: success value
        """
        params = str(fan_id) + "," + str(speed_percent)
        response = self._client.execute_command("set_subrack_fan_speed", params)
        self.logger.debug(
            "TpmDriver:"
            + response["command"]
            + ": "
            + response["status"]
            + " = "
            + response["retvalue"]
        )
        return True

    def set_subrack_fan_modes(
        self: SubrackDriver, fan_id: int, mode: ControlMode
    ) -> bool:
        """
        Set Fan Operational Mode for the subrack's fan.

        :param fan_id: id of the selected fan accepted value: 1-4
        :param mode: AUTO or MANUAL

        :return: success value
        """
        params = str(fan_id) + "," + str(mode)
        response = self._client.execute_command("set_fan_modes", params)
        self.logger.debug(
            "TpmDriver:"
            + response["command"]
            + ": "
            + response["status"]
            + " = "
            + response["retvalue"]
        )
        return True

    def set_power_supply_fan_speed(
        self: SubrackDriver, power_supply_fan_id: int, speed_percent: float
    ) -> bool:
        """
        Set the power supply  fan speed.

        :param power_supply_fan_id: power supply id from 0 to 2
        :param speed_percent: fan speed in percent

        :return: success value
        """
        params = str(power_supply_fan_id) + "," + str(speed_percent)
        response = self._client.execute_command("set_power_supply_fan_speed", params)
        self.logger.debug(
            "TpmDriver:"
            + response["command"]
            + ": "
            + response["status"]
            + " = "
            + response["retvalue"]
        )
        return True
