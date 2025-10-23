from dataclasses import dataclass, field
from typing import List, Union
import tango
from __future__ import annotations

class FirmwareThresholdsDbInterface:
    def __init__(self, device_name: str, thresholds: list[FirmwareThresholds], db_connection: tango.Database | None):
        self._device_name = device_name
        self._thresholds = thresholds
        self._db_connection = db_connection or tango.Database()
        self._sync_class_cache_with_db()

    def _sync_class_cache_with_db(self):
        firmware_thresholds = self._db_connection.get_device_attribute_property(self._device_name, self._thresholds.to_device_property_keys_only())
        self._thresholds.update_from_dict(firmware_thresholds["firmware_thresholds"])

    def write_threshold_to_db(self):
        self._db_connection.put_device_attribute_property(self._device_name, self._thresholds.to_device_property_dict())



@dataclass
class FirmwareThresholds:
    """
    Dataclass containing the firmware thresholds for the TPM.

    """

    
    _fpga1_warning_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _fpga1_alarm_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _fpga2_warning_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _fpga2_alarm_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _board_warning_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _board_alarm_threshold: Union[List[int], str] = field(default="Undefined", repr=False)


    def __post_init__(self):
        self.fpga1_warning_threshold = self._fpga1_warning_threshold
        self.fpga1_alarm_threshold = self._fpga1_alarm_threshold
        self.fpga2_warning_threshold = self._fpga2_warning_threshold
        self.fpga2_alarm_threshold = self._fpga2_alarm_threshold
        self.board_warning_threshold = self._board_warning_threshold
        self.board_alarm_threshold = self._board_alarm_threshold


    @staticmethod
    def _validate_threshold(value: int, name: str):
        if isinstance(value, str):
            if value != "Undefined":
                raise ValueError(f"{name} string value must be 'Undefined'")
        else:
            if not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a float or int")

    @property
    def fpga1_alarm_threshold(self) -> Union[List[int], str]:
        return self._fpga1_alarm_threshold

    @fpga1_alarm_threshold.setter
    def fpga1_alarm_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga1_alarm_threshold")
        self._fpga1_alarm_threshold = value
        
    @property
    def fpga1_warning_threshold(self) -> Union[List[int], str]:
        return self._fpga1_warning_threshold

    @fpga1_warning_threshold.setter
    def fpga1_warning_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga1_warning_threshold")
        self._fpga1_warning_threshold = value

    @property
    def fpga2_alarm_threshold(self) -> Union[List[int], str]:
        return self._fpga2_alarm_threshold

    @fpga2_alarm_threshold.setter
    def fpga2_alarm_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga2_alarm_threshold")
        self._fpga2_alarm_threshold = value

    @property
    def fpga2_warning_threshold(self) -> Union[List[int], str]:
        return self._fpga2_warning_threshold

    @fpga2_warning_threshold.setter
    def fpga2_warning_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga2_warning_threshold")
        self._fpga2_warning_threshold = value

    @property
    def board_warning_threshold(self) -> Union[List[int], str]:
        return self._board_warning_threshold

    @board_warning_threshold.setter
    def board_warning_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "board_warning_threshold")
        self._board_warning_threshold = value

    @property
    def board_alarm_threshold(self) -> Union[List[int], str]:
        return self._board_alarm_threshold

    @board_alarm_threshold.setter
    def board_alarm_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "board_alarm_threshold")
        self._board_alarm_threshold = value


    def to_device_property_dict(self) -> dict:
        """Return dict with keys and current values."""
        return {
            "firmware_thresholds": {
                "board_alarm_threshold": self.board_alarm_threshold,
                "board_warning_threshold": self.board_warning_threshold,
                "fpga2_warning_threshold": self.fpga2_warning_threshold,
                "fpga2_alarm_threshold": self.fpga2_alarm_threshold,
                "fpga1_warning_threshold": self.fpga1_warning_threshold,
                "fpga1_alarm_threshold": self.fpga1_alarm_threshold,
            }
        }

    def to_device_property_keys_only(self) -> dict:
        """Return dict with keys only, values replaced by None."""
        return {
            "firmware_thresholds": {
                "board_alarm_threshold": None,
                "board_warning_threshold": None,
                "fpga2_warning_threshold": None,
                "fpga2_alarm_threshold": None,
                "fpga1_warning_threshold": None,
                "fpga1_alarm_threshold": None
            }
        }
    
    def update_from_dict(self, thresholds: dict):
        """
        Update FirmwareThresholds properties from a Tango-style dict, e.g.:
        {'board_alarm_threshold': ['Undefined'], 'fpga1_alarm_threshold': ['80'], ...}
        """
        for key, raw_value in thresholds.items():
            if not hasattr(self, key):
                continue  # Skip unknown keys safely

            # 1. Unwrap list values like ['80'] -> '80'
            value = raw_value[0] if isinstance(raw_value, tango._tango.StdStringVector) else raw_value

            # 2. Convert all defined values to floats.
            if isinstance(value, str) and not value=="Undefined":
                if value.isdigit():
                    value = int(value)
                else:
                    value = float(value)

            print(f"{key=}, {value=}")
            # 3. Use property setter (preserves validation)
            setattr(self, key, value)
        