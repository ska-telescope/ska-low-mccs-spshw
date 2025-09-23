from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class FirmwareThresholds:
    _fpga1_temperature_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _fpga2_temperature_threshold: Union[List[int], str] = field(default="Undefined", repr=False)
    _board_temperature_threshold: Union[List[int], str] = field(default="Undefined", repr=False)

    def __post_init__(self):
        self.fpga1_temperature_threshold = self._fpga1_temperature_threshold
        self.fpga2_temperature_threshold = self._fpga2_temperature_threshold
        self.board_temperature_threshold = self._board_temperature_threshold

    @staticmethod
    def _validate_threshold(value: Union[List[int], str], name: str):
        if isinstance(value, str):
            if value != "Undefined":
                raise ValueError(f"{name} string value must be 'Undefined'")
        else:
            if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) for v in value)):
                raise ValueError(f"{name} must be 'Undefined' or a list of exactly two integers")

    @property
    def fpga1_temperature_threshold(self) -> Union[List[int], str]:
        return self._fpga1_temperature_threshold

    @fpga1_temperature_threshold.setter
    def fpga1_temperature_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga1_temperature_threshold")
        self._fpga1_temperature_threshold = value

    @property
    def fpga2_temperature_threshold(self) -> Union[List[int], str]:
        return self._fpga2_temperature_threshold

    @fpga2_temperature_threshold.setter
    def fpga2_temperature_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "fpga2_temperature_threshold")
        self._fpga2_temperature_threshold = value

    @property
    def board_temperature_threshold(self) -> Union[List[int], str]:
        return self._board_temperature_threshold

    @board_temperature_threshold.setter
    def board_temperature_threshold(self, value: Union[List[int], str]):
        self._validate_threshold(value, "board_temperature_threshold")
        self._board_temperature_threshold = value

    def to_device_property_dict(self) -> dict:
        """Return dict with keys and current values."""
        return {
            "firmware_thresholds": {
                "fpga1_temperature_threshold": self.fpga1_temperature_threshold,
                "fpga2_temperature_threshold": self.fpga2_temperature_threshold,
                "board_temperature_threshold": self.board_temperature_threshold
            }
        }

    def to_device_property_keys_only(self) -> dict:
        """Return dict with keys only, values replaced by None."""
        return {
            "firmware_thresholds": {
                "fpga1_temperature_threshold": "Undefined",
                "fpga2_temperature_threshold": "Undefined",
                "board_temperature_threshold": "Undefined"
            }
        }