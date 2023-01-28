"""A simple subrack simulator."""
from __future__ import annotations

import copy
import threading
from typing import Any, Final, Optional, TypedDict, cast

from .subrack_api import SubrackProtocol
from .subrack_data import FanMode, SubrackData

# https://github.com/python/typing/issues/182
JsonSerializable = Any


class SubrackSimulator(SubrackProtocol):
    """A simple simulator of a subrack management board web server."""

    class AttributeMetadataType(TypedDict):
        """Type for attribute metadata dictionary."""

        length: Optional[int]
        default: JsonSerializable
        writable: bool

    ATTRIBUTE_METADATA: Final[dict[str, AttributeMetadataType]] = {
        "tpm_present": {
            "length": SubrackData.TPM_BAY_COUNT,
            "default": [True] * SubrackData.TPM_BAY_COUNT,
            "writable": False,
        },
        "tpm_on_off": {
            "length": SubrackData.TPM_BAY_COUNT,
            "default": [False] * SubrackData.TPM_BAY_COUNT,
            "writable": False,
        },
        "backplane_temperatures": {
            "length": 2,
            "default": [38.0, 39.0],
            "writable": False,
        },
        "board_temperatures": {
            "length": 2,
            "default": [39.0, 40.0],
            "writable": False,
        },
        "board_current": {
            "length": None,
            "default": 1.1,
            "writable": False,
        },
        "power_supply_fan_speeds": {
            "length": 2,
            "default": [93.0, 94.0],
            "writable": False,
        },
        "power_supply_currents": {
            "length": 2,
            "default": [4.2, 5.8],
            "writable": False,
        },
        "power_supply_voltages": {
            "length": 2,
            "default": [12.0, 12.1],
            "writable": False,
        },
        "subrack_fan_speed_percent": {
            "length": 4,
            "default": [95.0, 96.0, 97.0, 98.0],
            "writable": False,
        },
        "subrack_fan_mode": {
            "length": 4,
            "default": [FanMode.AUTO, FanMode.AUTO, FanMode.AUTO, FanMode.AUTO],
            "writable": False,
        },
        "tpm_currents": {
            "length": 8,
            "default": [0.4] * 8,
            "writable": False,
        },
        # "tpm_temperatures": {  # Not implemented on SMB
        #     "length": 8,
        #     "default": [40.0] * 8,
        #     "writable": False,
        # },
        "tpm_voltages": {
            "length": 8,
            "default": [12.0] * 8,
            "writable": False,
        },
    }

    def __init__(self: SubrackSimulator, **kwargs: JsonSerializable) -> None:
        """
        Initialise a new instance.

        :param kwargs: initial values, different from the defaults, that
            the simulator should take.

        :raises AttributeError: if kwargs refer to an non-existent attribute.
        """
        unknown_names = [name for name in kwargs if name not in self.ATTRIBUTE_METADATA]
        if unknown_names:
            raise AttributeError(f"Unknown attributes: {','.join(unknown_names)}.")

        self._attribute_values: dict[str, JsonSerializable] = copy.deepcopy(kwargs)
        for attribute, metadata in self.ATTRIBUTE_METADATA.items():
            self._attribute_values.setdefault(attribute, metadata["default"])

        self._aborted_event = threading.Event()
        self._command_is_running = False
        self._command_duration: Final = 0.05

    def set_attribute(
        self: SubrackSimulator, name: str, value: JsonSerializable
    ) -> JsonSerializable:
        """
        Set the value of a simulator attribute.

        :param name: name of the simulator attribute to be set.
        :param value: new values for the simulator attribute

        :return: the new values for the attribute
        """
        special_set_method = getattr(self, f"_set_attribute_{name}", None)

        if special_set_method is None:
            return self._set_attribute(name, value)
        return special_set_method(value)

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

    def _set_attribute(
        self: SubrackSimulator,
        name: str,
        values: JsonSerializable,
        _force: bool = False,
    ) -> list[str]:
        if name not in self.ATTRIBUTE_METADATA:
            raise AttributeError(f"{name} not present")

        metadata = self.ATTRIBUTE_METADATA[name]
        if not metadata["writable"] and not _force:
            raise TypeError(f"Attempt to write read-only attribute {name}")
        if metadata["length"] is not None and len(values) != metadata["length"]:
            raise ValueError(f"Wrong number of values for attribute {name}")
        self._attribute_values[name] = values
        return values

    def get_attribute(self: SubrackSimulator, name: str) -> JsonSerializable:
        """
        Return the value of a simulator attribute.

        :param name: name of the simulator attribute to be returned.

        :return: the value of the attribute
        """
        special_get_method = getattr(self, f"_get_attribute_{name}", None)

        if special_get_method is None:
            return self._get_attribute(name)

        return special_get_method()

    def _get_attribute(self: SubrackSimulator, name: str) -> JsonSerializable:
        if name not in self.ATTRIBUTE_METADATA:
            raise AttributeError(f"{name} not present")
        return self._attribute_values[name]

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

    def _get_attribute_tpm_powers(self: SubrackSimulator) -> list[float]:
        return [
            current * voltage
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

    def _get_attribute_subrack_fan_speed(
        self: SubrackSimulator,
    ) -> list[float]:
        return [
            percent * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0
            for percent in self._attribute_values["subrack_fan_speed_percent"]
        ]

    def _command_completed(self: SubrackSimulator, _not_used: Optional[str]) -> bool:
        """
        Check if no command is currently running.

        :param _not_used: not used, should always be empty e.g. ""

        :return: False if a command is currently run; otherwise True.
        """
        assert not _not_used
        return not self._command_is_running

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
        fan_index = int(fan_str)  # input is 0-based, so no need for an offset
        speed = float(speed_str)
        self._attribute_values["subrack_fan_speed_percent"][fan_index] = speed

    def _set_subrack_fan_mode(self: SubrackSimulator, arg: str) -> None:
        (fan_str, mode_str) = arg.split(",")
        fan_index = int(fan_str)  # input is 0-based, so no need for an offset
        mode = FanMode[mode_str]
        self._attribute_values["subrack_fan_mode"][fan_index] = mode

    def _set_power_supply_fan_speed(self: SubrackSimulator, arg: str) -> None:
        (fan_str, speed_str) = arg.split(",")
        fan_index = int(fan_str)  # input is 0-based, so no need for an offset
        speed = float(speed_str)
        self._attribute_values["power_supply_fan_speeds"][fan_index] = speed

    def _async_turn_off_tpm(self: SubrackSimulator, arg: str) -> None:
        """
        Turn off a TPM.

        :param arg: number of the TPM to be turned off (in string form).
        """
        tpm_number = int(arg)  # input is 0-based, so no need for an offset
        cast(list[bool], self._attribute_values["tpm_on_off"])[tpm_number] = False

    def _async_turn_on_tpm(self: SubrackSimulator, arg: str) -> None:
        """
        Turn on a TPM.

        :param arg: number of the TPM to be turned on (in string form).
        """
        tpm_number = int(arg)  # input is 0-based, so no need for an offset
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
