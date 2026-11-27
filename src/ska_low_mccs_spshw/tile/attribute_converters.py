#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements simple type conversions relevant to Tile attributes."""
from __future__ import annotations

import functools
import itertools
import json
from typing import Any, Callable, TypeVar

import numpy as np

_T = TypeVar("_T")

__all__ = [
    "NumpyEncoder",
    "adc_pll_to_list",
    "adc_to_list",
    "clock_managers_count",
    "clock_managers_status",
    "clocks_to_list",
    "find_missing_values",
    "flatten_list",
    "lane_error_to_array",
    "none_if_missing",
    "serialise_np_object",
    "serialise_object",
    "udp_error_count_to_list",
]


class NumpyEncoder(json.JSONEncoder):
    """Converts numpy types to JSON."""

    # pylint: disable=arguments-renamed
    def default(self: NumpyEncoder, obj: Any) -> Any:
        """
        Encode numpy object.

        :param obj: the object to encode

        :returns: the encoded result.
        """
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, complex):
            return obj.real, obj.imag
        return json.JSONEncoder.default(self, obj)


def find_missing_values(val: Any, path: str = "") -> list[str]:
    """
    Find the locations of any ``None`` values within a nested structure.

    The tpm-api reports ``None`` for an individual entry (e.g. a single ADC)
    when reading it from hardware raised an exception. The converters in this
    module cannot represent such entries in a Tango attribute, so function
    `none_if_missing` uses this to detect them up front.

    :example:
        >>> find_missing_values({"ADC0": True, "ADC9": None})
        ['ADC9']
        >>> find_missing_values({"Core0": {"lane0": 0, "lane3": None}})
        ['Core0.lane3']
        >>> find_missing_values({"C2C_MMCM": (True, None)})
        ['C2C_MMCM[1]']

    :param val: the (possibly nested) dict/list/tuple to search.
    :param path: the location of ``val`` within the outermost structure,
        used to build the reported paths during recursion.

    :return: the path of each ``None`` found, or an empty list if none.
    """
    if val is None:
        return [path]
    # Recurse into containers, extending the path with ".key" for dicts
    # and "[index]" for sequences so the log pinpoints the bad entry.
    if isinstance(val, dict):
        return [
            missing
            for key, item in val.items()
            for missing in find_missing_values(
                item, f"{path}.{key}" if path else str(key)
            )
        ]
    if isinstance(val, (list, tuple)):
        return [
            missing
            for index, item in enumerate(val)
            for missing in find_missing_values(item, f"{path}[{index}]")
        ]
    return []


def none_if_missing(
    converter: Callable[[Any], _T],
) -> Callable[[Any], _T | None]:
    """
    Make a converter return ``None`` if its input has any ``None`` entries.

    The signal bus publishes a ``None`` from an attribute's ``to_tango``
    conversion with ``ATTR_INVALID`` quality. A warning naming the missing
    entries is logged each time in TPM-API.

    :param converter: the converter to wrap.

    :return: the wrapped converter.
    """

    @functools.wraps(converter)
    def _wrapper(val: Any) -> _T | None:
        missing = find_missing_values(val)
        if missing:
            return None
        return converter(val)

    return _wrapper


def flatten_list(val: list[list[Any]]) -> list[Any]:
    """
    Flatten list to 1 dimensional.

    :param val: the 2 dimensional list.

    :return: a 1 dimensional list.
    """
    return list(itertools.chain.from_iterable(val))


def serialise_object(val: dict[str, Any] | tuple[Any, Any]) -> str:
    """
    Serialise to a json string.

    :param val: A dictionary or tuple to serialise.

    :return: a json serialised string.
    """
    return json.dumps(val)


def serialise_np_object(val: dict[str, Any] | tuple[Any, Any]) -> str:
    """
    Serialise to a json string.

    :param val: A dictionary or tuple to serialise.

    :return: a json serialised string.
    """
    return json.dumps(val, cls=NumpyEncoder)


@none_if_missing
def adc_pll_to_list(val: dict[str, tuple[bool, bool]]) -> np.ndarray:
    """
    Flatten adc indexed dictionary to list.

    :param val: A dictionary indexed by ADC number.

    :return: a flattened list.
    """
    flattened_list = []
    for i in range(16):
        v = val[f"ADC{i}"]
        flattened_list.append((int(v[0]), int(v[1])))
    arr = np.array(flattened_list).T  # Transpose to get shape (2, 16)
    return arr


@none_if_missing
def adc_to_list(val: dict[str, bool]) -> list[int]:
    """
    Flatten adc indexed dictionary to list.

    :param val: A dictionary indexed by ADC number.

    :return: a flattened list.
    """
    flattened_list = []
    for i in range(16):
        v = val[f"ADC{i}"]
        flattened_list.append(int(v))
    return flattened_list


@none_if_missing
def udp_error_count_to_list(val: dict[str, int]) -> list[int]:
    """
    Flatten udp error count to 1d list.

    :param val: A dictionary indexed by ADC number.

    :return: a flattened list.
    """
    flattened_list: list[int] = []
    for lane_idx in range(4):
        flattened_list.append(int(val[f"lane{lane_idx}"]))
    return flattened_list


@none_if_missing
def lane_error_to_array(val: dict[str, dict[str, int | None]]) -> np.ndarray:
    """
    Flatten udp error count to 1d list.

    :param val: A dictionary indexed by ADC number.

    :return: a flattened list.
    """
    # [[Core0],[Core1]]
    result = [
        [core[f"lane{i}"] for i in range(8)]
        for core in [val[f"Core{j}"] for j in range(2)]
    ]

    # Convert to NumPy array if needed
    return np.array(result)


def _extract_mmcm_array(
    val: dict[str, tuple[bool, int]],
    index: int,
) -> np.ndarray:
    """
    Extract MMCM fields into a NumPy array.

    :param val: Dictionary.
    :param index: idx0 -> 'status' (bool), idx1 -> 'count' (int)

    :returns: np.ndarray with shape (3): 3 MMCM types
    """
    mmcm_keys = ("C2C_MMCM", "JESD_MMCM", "DSP_MMCM")
    data = []
    for mmcm in mmcm_keys:
        data.append(val[mmcm][index])
    return np.array(data, dtype=int)


@none_if_missing
def clock_managers_status(val: dict[str, tuple[bool, int]]) -> np.ndarray:
    """
    Extract MMCM 'status' values into a (3) NumPy array.

    :param val: the value

    :returns: the status of each clock
    """
    return _extract_mmcm_array(val, index=0)


@none_if_missing
def clock_managers_count(val: dict[str, tuple[bool, int]]) -> np.ndarray:
    """
    Extract MMCM 'count' values into a (3) NumPy array.

    :param val: the value

    :returns: the count of each clock
    """
    return _extract_mmcm_array(val, index=1)


@none_if_missing
def clocks_to_list(val: dict[str, bool]) -> list[int]:
    """
    Convert the clocks to a list.

    :param val: the value

    :returns: the clocks as a list
    """
    return [int(val["JESD"]), int(val["DDR"]), int(val["UDP"])]
