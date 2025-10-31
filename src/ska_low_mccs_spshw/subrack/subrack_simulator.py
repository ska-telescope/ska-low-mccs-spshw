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
import random
import threading
import time
from typing import Any, Callable, Final, Optional, TypedDict, cast

from .subrack_api import SubrackProtocol
from .subrack_data import FanMode, SubrackData

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
            "default": [True] + ([False] * (SubrackData.TPM_BAY_COUNT - 1)),
            "writable": False,
        },
        "tpm_on_off": {
            "length": SubrackData.TPM_BAY_COUNT,
            "default": [True] + ([False] * (SubrackData.TPM_BAY_COUNT - 1)),
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
        "cpld_pll_locked": {
            "length": None,
            "default": False,
            "writable": False,
        },
        "power_supply_fan_speeds": {
            "length": 2,
            "default": [93.0, 94.0],
            "writable": False,
        },
        "power_supply_currents": {
            "length": 2,
            "default": [2.2, 2.8],
            "writable": False,
        },
        "power_supply_voltages": {
            "length": 2,
            "default": [12.0, 12.1],
            "writable": False,
        },
        "subrack_fan_speeds_percent": {
            "length": 4,
            "default": [95.0, 96.0, 97.0, 98.0],
            "writable": False,
        },
        "subrack_fan_mode": {
            "length": 4,
            "default": [FanMode.AUTO, FanMode.AUTO, FanMode.AUTO, FanMode.AUTO],
            "writable": False,
        },
        "subrack_pll_locked": {
            "length": None,
            "default": False,
            "writable": False,
        },
        "subrack_timestamp": {
            "length": None,
            "default": 1234567890,
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
            "default": [5.0] * 8,
            "writable": False,
        },
        "board_info": {
            "length": None,
            "default": {
                "SMM": {
                    "EXT_LABEL_SN": "",
                    "EXT_LABEL_PN": "",
                    "SN": "",
                    "PN": "SMB",
                    "SMB_UPS_SN": "",
                    "HARDWARE_REV": "v1.2.4 ",
                    "BOARD_MODE": "SUBRACK",
                    "bios": "v1.6.0",
                    "bios_cpld": "",
                    "bios_mcu": "",
                    "bios_uboot": "",
                    "bios_krn": "",
                    "OS": "Debian GNU/Linux 10",
                    "OS_rev": "",
                    "OS_root": "",
                    "BOOT_SEL_KRN": 0,
                    "BOOT_SEL_FS": 0,
                    "CPLD_ip_address": "",
                    "CPLD_netmask": "",
                    "CPLD_gateway": "",
                    "CPLD_ip_address_eep": "",
                    "CPLD_netmask_eep": "",
                    "CPLD_gateway_eep": "",
                    "CPLD_MAC": "",
                    "CPU_ip_address": "",
                    "CPU_netmask": "",
                    "CPU_MAC": "",
                },
                "SUBRACK": {
                    "EXT_LABEL": "",
                    "SN": "",
                    "PN": "BACKPLANE",
                    "HARDWARE_REV": "v1.2.2",
                    "CPLD_ip_address_eep": "",
                    "CPLD_netmask_eep": "",
                    "CPLD_gateway_eep": "",
                },
                "PSM": {"EXT_LABEL": "", "SN": "", "PN": "", "HARDWARE_REV": ""},
            },
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
        self._network_jitter_limits: tuple[int, int] = (0, 0)  # ms

        self._aborted_event = threading.Event()
        self._command_is_running = False
        self._command_duration: Final = 0.05

    @apply_jitter
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

    @apply_jitter
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

    def _get_attribute_subrack_fan_speeds(
        self: SubrackSimulator,
    ) -> list[float]:
        return [
            percent * SubrackData.MAX_SUBRACK_FAN_SPEED / 100.0
            for percent in self._attribute_values["subrack_fan_speeds_percent"]
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
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        speed = float(speed_str)
        self._attribute_values["subrack_fan_speeds_percent"][fan_index] = speed

    def _set_fan_mode(self: SubrackSimulator, arg: str) -> None:
        (fan_str, mode_str) = arg.split(",")
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        mode = int(mode_str)  # FanMode[mode_str]
        self._attribute_values["subrack_fan_mode"][fan_index] = mode

    def _set_power_supply_fan_speed(self: SubrackSimulator, arg: str) -> None:
        (fan_str, speed_str) = arg.split(",")
        fan_index = int(fan_str) - 1  # input is 1-based, so need for an offset
        speed = float(speed_str)
        self._attribute_values["power_supply_fan_speeds"][fan_index] = speed

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
        return {
            "temperatures": {
                "SMM1": 40,
                "SMM2": 41,
                "BKPLN1": 39,
                "BKPLN2": 41,
            },
            "plls": {
                "BoardPllLock": True,
                "CPLDPllLock": True,
                "PllSource": None,
            },
            "psus": {
                "present": {
                    "PSU1": True,
                    "PSU2": True,
                },
                "busy": {
                    "PSU1": None,
                    "PSU2": None,
                },
                "off": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "vout_ov_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "iout_oc_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "vin_uv_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "temp_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "cml_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "vout_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "iout_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "input_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "pwr_gd": {
                    "PSU1": True,
                    "PSU2": True,
                },
                "fan_fault": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "other": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "unknown": {
                    "PSU1": False,
                    "PSU2": False,
                },
                "voltage_out": {
                    "PSU1": 12.0,
                    "PSU2": 12.1,
                },
                "power_out": {
                    "PSU1": 4.2 * 12,
                    "PSU2": 5.8 * 12.1,
                },
                "voltage_in": {
                    "PSU1": 230,
                    "PSU2": 230,
                },
                "power_in": {
                    "PSU1": 300,
                    "PSU2": 300,
                },
                "fan_speed": {
                    "PSU1": 90.0,
                    "PSU2": 100.0,
                },
                "temp_inlet": {
                    "PSU1": 20,
                    "PSU2": 21,
                },
                "temp_fet": {
                    "PSU1": 30,
                    "PSU2": 31,
                },
            },
            "pings": {
                "pings_CPLD": True,
            },
            "slots": {
                "presence": {
                    "SLOT1": False,
                    "SLOT2": True,
                    "SLOT3": False,
                    "SLOT4": False,
                    "SLOT5": True,
                    "SLOT6": False,
                    "SLOT7": False,
                    "SLOT8": False,
                },
                "on": {
                    "SLOT1": False,
                    "SLOT2": False,
                    "SLOT3": False,
                    "SLOT4": False,
                    "SLOT5": False,
                    "SLOT6": False,
                    "SLOT7": False,
                    "SLOT8": False,
                },
                "voltages": {
                    "SLOT1": 12.0,
                    "SLOT2": 12.0,
                    "SLOT3": 12.0,
                    "SLOT4": 12.0,
                    "SLOT5": 12.0,
                    "SLOT6": 12.0,
                    "SLOT7": 12.0,
                    "SLOT8": 12.0,
                },
                "powers": {
                    "SLOT1": 0.4 * 12.0,
                    "SLOT2": 0.4 * 12.0,
                    "SLOT3": 0.4 * 12.0,
                    "SLOT4": 0.4 * 12.0,
                    "SLOT5": 0.4 * 12.0,
                    "SLOT6": 0.4 * 12.0,
                    "SLOT7": 0.4 * 12.0,
                    "SLOT8": 0.4 * 12.0,
                },
                "pings": {
                    "SLOT1": True,
                    "SLOT2": True,
                    "SLOT3": True,
                    "SLOT4": True,
                    "SLOT5": True,
                    "SLOT6": True,
                    "SLOT7": True,
                    "SLOT8": True,
                },
            },
            "internal_voltages": {
                "V_POWERIN": 12.0,
                "V_SOC": 1.35,
                "V_ARM": 1.35,
                "V_DDR": 1.35,
                "V_2V5": 2.5,
                "V_1V1": 1.1,
                "V_CORE": 1.2,
                "V_1V5": 1.5,
                "V_3V3": 3.3,
                "V_5V": 5.0,
                "V_3V": 3.0,
                "V_2V8": 2.8,
            },
            "fans": {
                "speed": {
                    "FAN1": 1,
                    "FAN2": 1,
                    "FAN3": 1,
                    "FAN4": 1,
                },
                "pwm_duty": {
                    "FAN1": 95,
                    "FAN2": 96,
                    "FAN3": 97,
                    "FAN4": 98,
                },
                "mode": {
                    "FAN1": FanMode.AUTO,
                    "FAN2": FanMode.AUTO,
                    "FAN3": FanMode.AUTO,
                    "FAN4": FanMode.AUTO,
                },
            },
        }
