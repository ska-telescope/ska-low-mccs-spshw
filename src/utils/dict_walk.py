# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Lookup of values in nested dictionaries."""
from __future__ import annotations

from typing import Any, Optional

__all__ = ["walk"]


def walk(data: Optional[dict], path: tuple[str, ...]) -> Any:
    """
    Follow a path of keys into a nested dictionary.

    :param data: the dictionary to walk, or ``None``.
    :param path: the keys to follow, outermost first.

    :return: the value at the end of the path, or ``None`` when any level of
        the path is missing.
    """
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value
