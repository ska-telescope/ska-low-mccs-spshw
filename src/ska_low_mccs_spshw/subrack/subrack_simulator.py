#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""A simple subrack simulator."""
from __future__ import annotations

import copy
import functools
import json
import random
import threading
import time
from collections.abc import Iterator
from typing import Any, Callable, Final, Optional, cast

from .subrack_api import CommandResult, SubrackProtocol
from .subrack_data import SubrackData
from .subrack_simulator_data import (
    ATTRIBUTE_METADATA,
    COMMANDS,
    HEALTH_STATUS,
    PLL_PHASE_OFFSET_BITS,
    PPS_PHASE_WINDOW_DEFAULT,
    PPS_PHASE_WINDOW_MAX,
    SUPPORTED_API_VERSIONS,
)

# https://github.com/python/typing/issues/182
JsonSerializable = Any


def apply_jitter(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Apply a simulated network jitter to the component.

    This will apply a simulated jitter to the decorated method.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @apply_jitter
        def get_attribute(self, name):
            ...

    :param func: the wrapped function

    :return: the wrapped function.
    """

    @functools.wraps(func)
    def inner(
        subrack_simulator: SubrackSimulator,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Apply a jitter if defined before calling method.

        :param subrack_simulator: the subrack simulator this is applied to
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :return: whatever the wrapped function returns
        """
        if subrack_simulator._network_jitter_limits:
            min_jitter, max_jitter = subrack_simulator._network_jitter_limits
            if min_jitter and max_jitter:
                sleep_time = random.randrange(min_jitter, max_jitter) / 1000
                time.sleep(sleep_time)
        return func(subrack_simulator, *args, **kwargs)

    return inner


# pylint: disable=too-many-instance-attributes
class SubrackSimulator(SubrackProtocol):
    """A simple simulator of a subrack management board web server."""

    def __init__(
        self: SubrackSimulator,
        api_version: str = "1.6.0",
        **kwargs: JsonSerializable,
    ) -> None:
        """
        Initialise a new instance.

        :param api_version: the version of the subrack web API that the
            simulator should emulate. This also sets the BIOS version
            reported in ``board_info``.
        :param kwargs: initial values, different from the defaults, that
            the simulator should take.

        :raises AttributeError: if kwargs refer to an non-existent attribute.
        :raises ValueError: if the API version is not supported.
        """
        if api_version not in SUPPORTED_API_VERSIONS:
            raise ValueError(
                f"Unsupported API version {api_version}; "
                f"must be one of {', '.join(SUPPORTED_API_VERSIONS)}."
            )
        self._api_version: Final = api_version

        self.ATTRIBUTE_METADATA = ATTRIBUTE_METADATA[api_version]
        self.ATTRIBUTES = self.ATTRIBUTE_METADATA.keys()
        self.COMMANDS = COMMANDS[api_version]
        self._health_status = HEALTH_STATUS[api_version]

        unknown_names = [name for name in kwargs if name not in self.ATTRIBUTE_METADATA]
        if unknown_names:
            raise AttributeError(f"Unknown attributes: {','.join(unknown_names)}.")

        self._attribute_values: dict[str, JsonSerializable] = copy.deepcopy(kwargs)
        for attribute, metadata in self.ATTRIBUTE_METADATA.items():
            self._attribute_values.setdefault(attribute, metadata["default"])

        # The BIOS version is how clients tell which API version they are
        # talking to, so it must always agree with the emulated API version.
        board_info = copy.deepcopy(self._attribute_values["board_info"])
        board_info["SMM"]["bios"] = f"v{api_version}"
        self._attribute_values["board_info"] = board_info

        self._network_jitter_limits: tuple[int, int] = (0, 0)  # ms
        self._failing_attributes: set[str] = set()

        self._aborted_event = threading.Event()
        self._command_is_running = False
        self._command_duration: Final = 0.05

        self._pll_phase_offset = 0  # ps
        self._pps_phase_window = PPS_PHASE_WINDOW_DEFAULT  # samples

    @apply_jitter
    def set_attribute(
        self: SubrackSimulator, name: str, value: JsonSerializable
    ) -> JsonSerializable:
        """
        Set the value of a simulator attribute.

        :param name: name of the simulator attribute to be set.
        :param value: new values for the simulator attribute

        :raises AttributeError: If name is not a valid attribute
        :return: the new values for the attribute
        """
        if name not in self.ATTRIBUTES:
            raise AttributeError(f"Attribute {name} not present")

        special_set_method = getattr(self, f"_set_attribute_{name}", None)

        if special_set_method is None:
            return self._set_attribute(name, value)
        return special_set_method(value)

    @property
    def api_version(self: SubrackSimulator) -> str:
        """
        Return the version of the subrack web API that this simulator emulates.

        :return: the emulated API version, e.g. "1.8.0".
        """
        return self._api_version

    @property
    def network_jitter_limits(self: SubrackSimulator) -> tuple[int, int]:
        """
        Return the max network jitter in miliseconds.

        :return: the maximum network jitter in milliseconds.
        """
        return self._network_jitter_limits

    @network_jitter_limits.setter
    def network_jitter_limits(self: SubrackSimulator, jitter: tuple[int, int]) -> None:
        """
        Return the max network jitter in milliseconds.

        :param jitter: the new maximum simulated network jitter in
            milliseconds.

        :raises ValueError: If te limits are not in the correct format.
        """
        try:
            min_jitter, max_jitter = jitter
        except ValueError as e:
            raise e
        if (max_jitter or min_jitter) and max_jitter < min_jitter:
            raise ValueError("First item must have value lower than the second")
        if max_jitter < 0 or min_jitter < 0:
            raise ValueError("Values must be positive.")
        if max_jitter > 20_000 or min_jitter > 20_000:
            raise ValueError("Value too large, must be less than 20,000 miliseconds")

        self._network_jitter_limits = (min_jitter, max_jitter)

    def simulate_attribute(
        self: SubrackSimulator, name: str, values: JsonSerializable
    ) -> JsonSerializable:
        """
        Simulate a change in attribute value.

        :param name: name of the simulator attribute to be set.
        :param values: new values for the simulator attribute

        :return: the new values for the attribute
        """
        special_simulate_method = getattr(self, f"_simulate_{name}", None)

        if special_simulate_method is None:
            return self._set_attribute(name, values, _force=True)
        return special_simulate_method(values)

    def simulate_attribute_failure(
        self: SubrackSimulator, name: str, failing: bool = True
    ) -> None:
        """
        Simulate a failure to read an attribute.

        While an attribute is failing, every read of it raises an
        exception, which the web API reports as an ERROR response.

        :param name: name of the simulator attribute.
        :param failing: whether reads of the attribute should fail.

        :raises AttributeError: if the attribute does not exist.
        """
        if name not in self.ATTRIBUTES and not hasattr(self, f"_get_attribute_{name}"):
            raise AttributeError(f"Attribute {name} not present")
        if failing:
            self._failing_attributes.add(name)
        else:
            self._failing_attributes.discard(name)

    def _set_attribute(
        self: SubrackSimulator,
        name: str,
        values: JsonSerializable,
        _force: bool = False,
    ) -> list[str]:
        """
        Set the value of an attribute.

        :param name: the name of the attribute
        :param values: the values to set the attribute to
        :param _force: set to True to override read only attributes

        :raises AttributeError: If this is not a valid attribute
        :raises TypeError: If this is a read only attribute and _force is False
        :raises ValueError: If the number of values doesn't mathc the attribute

        :returns: values
        """
        if name not in self.ATTRIBUTES:
            raise AttributeError(f"Attribute {name} not present")

        metadata = self.ATTRIBUTE_METADATA[name]
        if not metadata["writable"] and not _force:
            raise TypeError(f"Attempt to write read-only attribute {name}")
        if metadata["length"] is not None and len(values) != metadata["length"]:
            raise ValueError(f"Wrong number of values for attribute {name}: {values}")
        self._attribute_values[name] = values
        return values

    def _set_attribute_tpm_currents(self, value: str) -> list[str]:
        """
        Set the tpm currents attribute.

        :param value: The value of the tpm_currents

        :returns: The values

        """
        return self._set_attribute("tpm_currents", json.loads(value))

    def _set_attribute_tpm_voltages(self, value: str) -> list[str]:
        """
        Set the tpm voltages attribute.

        :param value: The value of the tpm_voltages

        :returns: The values

        """
        return self._set_attribute("tpm_voltages", json.loads(value))

    @apply_jitter
    def get_attribute(self: SubrackSimulator, name: str) -> JsonSerializable:
        """
        Return the value of a simulator attribute.

        :param name: name of the simulator attribute to be returned.

        :return: the value of the attribute

        :raises RuntimeError: if a failure of the attribute is being
            simulated.
        """
        if name in self._failing_attributes:
            raise RuntimeError(f"Failed to read attribute {name}")

        special_get_method = getattr(self, f"_get_attribute_{name}", None)

        if special_get_method is None:
            return self._get_attribute(name)

        return special_get_method()

    def _get_attribute(self: SubrackSimulator, name: str) -> JsonSerializable:
        if name not in self.ATTRIBUTES:
            raise AttributeError(f"Attribute {name} not present")

        value = self._attribute_values[name]
        if isinstance(value, Iterator):
            return next(value)
        return value

    @apply_jitter
    def execute_command(
        self: SubrackSimulator, name: str, argument: Optional[JsonSerializable]
    ) -> JsonSerializable:
        """
        Execute a command on the subrack hardware/simulator.

        It works by checking for a method named f"_{name}"; that is, if
        the command name is "turn_on_tpms", then it checks for a method
        named "_turn_on_tpms". If it finds such a method, it calls it
        with the provided argument, and returns the return value.

        Otherwise, it checks for a method named f"_async_{name}; for
        example, "_async_turn_on_tpms". If it finds such a method, it
        simulates a long running command by returning "STARTED", then
        letting a little time pass, then invoking the method.

        :param name: name of the command to execute.
        :param argument: argument to the command.

        :return: the return value. For synchronous commands, this is the
            returned value of the fully executed command. For
            asynchronous commands, this is the string "STARTED" or
            "FAILED".

        :raises AttributeError: if the command method does not exist in
            the simulator.
        """
        if name not in self.COMMANDS:
            raise AttributeError(f"Command {name} not implemented")

        command_method = getattr(self, f"_{name}", None)
        if command_method is not None:
            return command_method(argument)

        command_method = getattr(self, f"_async_{name}", None)
        if command_method is not None:
            if self._command_is_running:
                return "FAILED"
            self._command_is_running = True

            def simulate_async_command() -> None:
                if self._aborted_event.wait(self._command_duration):
                    self._aborted_event.clear()
                else:
                    assert command_method is not None  # for the type checker
                    command_method(argument)
                self._command_is_running = False

            threading.Thread(target=simulate_async_command).start()
            return "STARTED"

        raise AttributeError(f"Unknown command {name}.")

    def _get_attribute_tpm_powers(self: SubrackSimulator) -> list[float | None]:
        if "tpm_currents" not in self.ATTRIBUTES:
            return self._get_attribute("tpm_powers")
        return [
            None if current is None or voltage is None else current * voltage
            for current, voltage in zip(
                self._attribute_values["tpm_currents"],
                self._attribute_values["tpm_voltages"],
            )
        ]

    def _get_attribute_power_supply_powers(self: SubrackSimulator) -> list[float]:
        return [
            current * voltage
            for current, voltage in zip(
                self._attribute_values["power_supply_currents"],
                self._attribute_values["power_supply_voltages"],
            )
        ]

    def _get_attribute_subrack_fan_speeds(
        self: SubrackSimulator,
    ) -> list[float]:
        self._attribute_values["subrack_fan_speeds"] = [
            percent * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0
            for percent in self._attribute_values["subrack_fan_speeds_percent"]
        ]
        return self._attribute_values["subrack_fan_speeds"]

    def _list_commands(self: SubrackSimulator, _not_used: Optional[str]) -> list[str]:
        """
        List the commands that the simulator accepts.

        :param _not_used: not used, should always be empty e.g. ""

        :return: the command names.
        """
        assert not _not_used
        return list(self.COMMANDS)

    def _command_completed(
        self: SubrackSimulator, _not_used: Optional[str]
    ) -> bool | CommandResult:
        """
        Check if no command is currently running.

        From API 1.8.0, the response also says whether the command failed;
        simulated commands never fail.

        :param _not_used: not used, should always be empty e.g. ""
        :return: False if a command is currently run; otherwise True.
        """
        assert not _not_used
        completed = not self._command_is_running
        if self._api_version == "1.6.0":
            return completed
        return CommandResult(
            retvalue=completed,
            fields={"failed": False, "info": "command_completed completed OK"},
        )

    def _abort_command(self: SubrackSimulator, _not_used: Optional[str]) -> None:
        """
        Abort any currently running command.

        :param _not_used: not used, should always be empty e.g. ""
        """
        assert not _not_used
        if self._command_is_running:
            self._aborted_event.set()

    def _set_subrack_fan_speed(self: SubrackSimulator, arg: str) -> None:
        (fan_str, speed_str) = arg.split(",")
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        speed = float(speed_str)
        # On hardware we observe that when we change either fan 1 or fan 2
        # that the speed of both fans change. Similarly for 3 and 4.
        if fan_index in (0, 1):
            self._attribute_values["subrack_fan_speeds_percent"][0] = speed
            self._attribute_values["subrack_fan_speeds_percent"][1] = speed
        elif fan_index in (2, 3):
            self._attribute_values["subrack_fan_speeds_percent"][2] = speed
            self._attribute_values["subrack_fan_speeds_percent"][3] = speed

    def _set_fan_mode(self: SubrackSimulator, arg: str) -> None:
        (fan_str, mode_str) = arg.split(",")
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        mode = int(mode_str)  # FanMode[mode_str]
        # On hardware we observe that when we change either fan 1 or fan 2
        # that the mode of both fans change. Similarly for 3 and 4.
        if fan_index in (0, 1):
            self._attribute_values["subrack_fan_mode"][0] = mode
            self._attribute_values["subrack_fan_mode"][1] = mode
        elif fan_index in (2, 3):
            self._attribute_values["subrack_fan_mode"][2] = mode
            self._attribute_values["subrack_fan_mode"][3] = mode

    def _set_power_supply_fan_speed(self: SubrackSimulator, arg: str) -> None:
        (fan_str, speed_str) = arg.split(",")
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        speed = float(speed_str)
        self._attribute_values["power_supply_fan_speeds"][fan_index] = speed

    def _set_pll_phase_offset(self: SubrackSimulator, arg: str) -> None:
        """
        Set the PLL phase offset.

        :param arg: the offset in ps, a whole number.

        :raises ValueError: if the offset is not a whole number, or does not
            fit the PLL's offset register.
        """
        try:
            phase_offset = int(arg)
        except ValueError as error:
            # The API's message says floats are expected, but it parses ints.
            raise ValueError(f"Invalid parameter (exp: float, got {arg})") from error
        limit = 2 ** (PLL_PHASE_OFFSET_BITS - 1)
        if not -limit <= phase_offset < limit:
            raise ValueError(
                f"Value {phase_offset} is out of range for a "
                f"{PLL_PHASE_OFFSET_BITS}-bit signed integer "
                f"({-limit} to {limit - 1})."
            )
        self._pll_phase_offset = phase_offset

    def _get_pll_phase_offset(self: SubrackSimulator, _not_used: Optional[str]) -> int:
        """
        Return the PLL phase offset.

        :param _not_used: not used, should always be empty e.g. ""

        :return: the offset in ps.
        """
        return self._pll_phase_offset

    def _set_pps_phase_window(self: SubrackSimulator, arg: str) -> None:
        """
        Set how many samples the PPS phase is averaged over.

        :param arg: the window size in samples, a whole number.

        :raises ValueError: if the size is not a whole number, or is out of
            range.
        """
        try:
            samples = int(arg)
        except ValueError as error:
            raise ValueError(f"Invalid parameter (exp: int, got {arg})") from error
        if not 1 <= samples <= PPS_PHASE_WINDOW_MAX:
            raise ValueError(
                "PPS phase window must be between 1 and "
                f"{PPS_PHASE_WINDOW_MAX} samples"
            )
        self._pps_phase_window = samples

    def _get_pps_phase_window(self: SubrackSimulator, _not_used: Optional[str]) -> int:
        """
        Return how many samples the PPS phase is averaged over.

        :param _not_used: not used, should always be empty e.g. ""

        :return: the window size in samples.
        """
        return self._pps_phase_window

    def _async_turn_off_tpm(self: SubrackSimulator, arg: str) -> None:
        """
        Turn off a TPM.

        :param arg: number of the TPM to be turned off (in string form).
        """
        tpm_number = int(arg) - 1  # input is 1-based, so need for an offset
        cast(list[bool], self._attribute_values["tpm_on_off"])[tpm_number] = False

    def _async_turn_on_tpm(self: SubrackSimulator, arg: str) -> None:
        """
        Turn on a TPM.

        :param arg: number of the TPM to be turned on (in string form).
        """
        tpm_number = int(arg) - 1  # input is 1-based, so need for an offset
        cast(list[bool], self._attribute_values["tpm_on_off"])[tpm_number] = True

    def _async_turn_off_tpms(self: SubrackSimulator, _not_used: Optional[str]) -> None:
        """
        Turn off all TPMs.

        :param _not_used: not used, should always be empty e.g. ""
        """
        self._attribute_values["tpm_on_off"] = [False] * SubrackData.TPM_BAY_COUNT

    def _async_turn_on_tpms(self: SubrackSimulator, _not_used: Optional[str]) -> None:
        """
        Turn on all TPM.

        :param _not_used: not used, should always be empty e.g. ""
        """
        self._attribute_values["tpm_on_off"] = [True] * SubrackData.TPM_BAY_COUNT

    def _get_health_status(self: SubrackSimulator, arg: str) -> dict:
        psu_currents = cast(
            list[float], self._attribute_values["power_supply_currents"]
        )
        psu_voltages = cast(
            list[float], self._attribute_values["power_supply_voltages"]
        )
        board_pll_locked = (
            None
            if "subrack_pll_locked" in self._failing_attributes
            else self._attribute_values["subrack_pll_locked"]
        )
        return self._health_status(
            psu_currents=psu_currents,
            psu_voltages=psu_voltages,
            board_pll_locked=board_pll_locked,
            tpm_present=self._attribute_values["tpm_present"],
            tpm_on_off=self._attribute_values["tpm_on_off"],
            tpm_powers=self._get_attribute_tpm_powers(),
        )
