#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements a FirmwareThresholds dataclass and an interface to db."""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Union

import tango
from tango import Database

__all__: list[str] = [
    "FirmwareThresholdsDbAdapter",
    "FirmwareThresholds",
    "TEMPERATURE_KEYS",
    "VOLTAGE_KEYS",
    "CURRENT_KEYS",
]

TEMPERATURE_KEYS: Final[list[str]] = ["fpga1", "fpga2", "board"]
VOLTAGE_KEYS: Final[list[str]] = [
    "MGT_AVCC",
    "MGT_AVTT",
    "SW_AVDD1",
    "SW_AVDD2",
    "AVDD3",
    "MAN_1V2",
    "DDR0_VREF",
    "DDR1_VREF",
    "VM_DRVDD",
    "VIN",
    "MON_3V3",
    "MON_1V8",
    "MON_5V0",
]
CURRENT_KEYS: Final[list[str]] = ["FE0_mVA", "FE1_mVA"]


class FirmwareThresholdsDbAdapter:
    """Tango DB interface for reading/writing FirmwareThresholds."""

    def __init__(
        self: FirmwareThresholdsDbAdapter,
        device_name: str,
        thresholds: FirmwareThresholds,
        db_connection: Database | None = None,
    ) -> None:
        """
        Initialise an interface to database.

        :param device_name: the trl of the device these thresholds belong to.
        :param thresholds: A class containing the FirmwareThresholds.
        :param db_connection: An optional database connection to inject for
            testing.
        """
        self._device_name = device_name
        self._thresholds = thresholds
        self._db_connection = db_connection or Database()
        self._sync_class_cache_with_db()

    def _sync_class_cache_with_db(self: FirmwareThresholdsDbAdapter) -> None:
        """Update threshold cache from database."""
        print("Syncing class cache with DB...")
        firmware_thresholds = self._db_connection.get_device_attribute_property(
            self._device_name, self._thresholds.to_device_property_keys_only()
        )
        self._thresholds.update_from_dict(firmware_thresholds["temperatures"])
        self._thresholds.update_from_dict(firmware_thresholds["voltages"])
        self._thresholds.update_from_dict(firmware_thresholds["currents"])
        print("Thresholds synced with DB.")

    def write_threshold_to_db(self: FirmwareThresholdsDbAdapter) -> None:
        """Put thresholds into database."""
        self._db_connection.put_device_attribute_property(
            self._device_name, self._thresholds.to_device_property_dict()
        )

    def resync_with_db(self: FirmwareThresholdsDbAdapter) -> None:
        """Resync class with db values."""
        self._sync_class_cache_with_db()


# pylint: disable=too-many-instance-attributes
@dataclass
class FirmwareThresholds:
    """Dataclass containing firmware thresholds for the TPM."""

    # --------------------------
    # Temperatures
    # --------------------------
    _fpga1_warning_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _fpga1_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _fpga2_warning_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _fpga2_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _board_warning_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _board_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )

    # --------------------------
    # Voltages
    # --------------------------
    _MGT_AVCC_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MGT_AVCC_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MGT_AVTT_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MGT_AVTT_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _SW_AVDD1_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _SW_AVDD1_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _SW_AVDD2_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _SW_AVDD2_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _AVDD3_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _AVDD3_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MAN_1V2_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MAN_1V2_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _DDR0_VREF_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _DDR0_VREF_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _DDR1_VREF_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _DDR1_VREF_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _VM_DRVDD_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _VM_DRVDD_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _VIN_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _VIN_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_3V3_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_3V3_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_1V8_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_1V8_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_5V0_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _MON_5V0_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )

    # --------------------------
    # Currents
    # --------------------------
    _FE0_mVA_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _FE0_mVA_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _FE1_mVA_min_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )
    _FE1_mVA_max_alarm_threshold: Union[int, float, str] = field(
        default="Undefined", repr=False
    )

    # Make group_map an instance attribute with default_factory
    group_map: dict = field(init=False, repr=False)

    def __post_init__(self: FirmwareThresholds) -> None:
        """Initialize thresholds for all categories."""
        self.group_map = {}

        raw_groups = {
            "temperatures": self._get_temperature_keys(),
            "voltages": self._get_voltage_keys(),
            "currents": self._get_current_keys(),
        }

        for group_name, keys in raw_groups.items():
            self.group_map[group_name] = []
            for key in keys:
                for suffix in self._get_suffixes_for(key):
                    field_name = f"_{key}_{suffix}"
                    if hasattr(self, field_name):
                        # Set the actual attribute
                        setattr(self, f"{key}_{suffix}", getattr(self, field_name))
                        # Store the f"{key}_{suffix}" string in the group map
                        self.group_map[group_name].append(f"{key}_{suffix}")

    # --------------------------
    # Utility
    # --------------------------
    def _get_temperature_keys(self: FirmwareThresholds) -> list[str]:
        return TEMPERATURE_KEYS

    def _get_voltage_keys(self: FirmwareThresholds) -> list[str]:
        return VOLTAGE_KEYS

    def _get_current_keys(self: FirmwareThresholds) -> list[str]:
        return CURRENT_KEYS

    def _get_suffixes_for(self: FirmwareThresholds, key: str) -> list[str]:
        if key in self._get_temperature_keys():
            return ["warning_threshold", "alarm_threshold"]
        return ["min_alarm_threshold", "max_alarm_threshold"]

    # --------------------------
    # Validation helper
    # --------------------------
    @staticmethod
    def _validate_threshold(value: Union[int, float, str], name: str) -> None:
        """
        Validate the threshold value.

        :param value: The new threshold value
        :param name: The threshold name.

        :raises ValueError: when validation fails.
        """
        if isinstance(value, str):
            if value != "Undefined":
                raise ValueError(f"{name} string value must be 'Undefined'")
        elif not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be int, float, or 'Undefined'")

    # --------------------------
    # Dynamic getter/setter
    # --------------------------
    def __getattr__(self: FirmwareThresholds, name: str) -> Any:
        """
        Get a threshold dynamically.

        :param name: the name of the threshold.

        :returns: the threshold value.
        :raises AttributeError: when the attribute is not defined.
        """
        attr = f"_{name}"
        if attr in self.__dataclass_fields__:
            return getattr(self, attr)
        raise AttributeError(f"{name} not found")

    def __setattr__(self: FirmwareThresholds, name: str, value: Any) -> None:
        """
        Set a new threshold dynamically.

        :param name: the threshold name
        :param value: the threshold value.
        """
        attr = f"_{name}"
        if attr in self.__dataclass_fields__:
            self._validate_threshold(value, name)
            object.__setattr__(self, attr, value)
        else:
            object.__setattr__(self, name, value)

    def to_device_property_dict(self: FirmwareThresholds) -> dict:
        """
        Return dict of all thresholds with current values.

        :returns: a dictionary with structure required
            for loading into database
        """
        data = {}
        for group_name, field_names in self.group_map.items():
            group_data = {}
            for field_name in field_names:
                group_data[field_name] = getattr(self, field_name)

            data[group_name] = group_data
        return data

    def to_device_property_keys_only(self) -> dict:
        """
        Return dict of all threshold keys with None values.

        :returns: a dictionary with structure required
            for reading from the database.
        """
        data: dict = {}
        for group_name, field_names in self.group_map.items():
            group_data: dict[str, None] = {}
            for field_name in field_names:
                group_data[field_name] = None
            data[group_name] = group_data
        return data

    def update_from_dict(self, thresholds: dict[str, tango.StdStringVector]) -> None:
        """
        Update FirmwareThresholds properties from a Tango-style dict.

        The tango style dict is dict<str, dict<str, seq<str>>>

        Example input:
            {'fpga1_alarm_threshold': ['80'], 'VIN_max_alarm_threshold': ['5.0']}


        :param thresholds: the tango dictionary.

        :raises ValueError: In the case value was not
            Undefined or a numeric value.
        """
        for key, raw_value in thresholds.items():
            if not hasattr(self, key):
                print(f"Unrecognised {key=}, skipping!")
                continue

            # For typehint
            value: str | int | float

            # Unwrap lists (like ['80'], ['Undefined'], ['8.0'])
            if isinstance(raw_value, (list, tuple)):
                value = raw_value[0] if raw_value else "Undefined"
            elif hasattr(raw_value, "__iter__") and not isinstance(raw_value, str):
                # handles Tango tango.StdStringVector
                value = next(iter(raw_value), "Undefined")
            else:
                value = raw_value

            # Convert to int/float where possible
            if isinstance(value, str) and value != "Undefined":
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError as ex:
                    raise ValueError(
                        f"Invalid numeric value for {key}: {value}"
                    ) from ex

            # Set the value using property setter for validation
            print(f"Updating {key} = {value}")
            setattr(self, key, value)
