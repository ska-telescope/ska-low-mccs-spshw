#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
An snmpsim variation module that switches the outlets of a simulated PDU.

snmpsim serves recorded data, so a write to an outlet's control object would
not change that outlet's state object. This module joins the two. Each tagged
record names its role and its outlet, for example
``1.3.6.1.4.1.38446.1.5.4.1.4.1.3|2:pdu|role=state,port=3,value=1``.

- A write to a ``control`` record sets the state of its outlet.
- A read of a ``state`` record gives that state.
- A read of a ``control`` record gives the command that matches the state.

The values are the model's, from the module options. For example
``--variation-module-options=pdu:on:2,off:1,state_on:1,state_off:0``.

snmpsim loads this file itself rather than importing it. It needs only the
``init``, ``variate`` and ``shutdown`` functions. The module keeps its state in
module variables rather than in the contexts snmpsim provides, so it reads as
plain Python.
"""
from __future__ import annotations

from typing import Any

_settings: dict[str, int] = {}
_states: dict[str, int] = {}


def _options(text: str, separator: str) -> dict[str, str]:
    """
    Split a list of options, such as ``a:1,b:2``, into a dictionary.

    :param text: the options.
    :param separator: the separator between each key and its value.

    :return: each option's value, by key.
    """
    return dict(item.split(separator, 1) for item in text.split(",") if item)


def init(**context: Any) -> None:
    """
    Take the model's control and state values from the module options.

    :param context: the snmpsim context, whose ``options`` holds the values.
    """
    _settings.clear()
    _states.clear()
    for key, value in _options(context["options"], ":").items():
        _settings[key] = int(value)


def variate(oid: Any, tag: str, value: str, **context: Any) -> tuple[Any, str, Any]:
    """
    Read or write one tagged record.

    :param oid: the object identifier of the record.
    :param tag: the record's type tag.
    :param value: the record's options, as the data file gives them.
    :param context: the snmpsim context of this request.

    :return: the object identifier, the type tag and the value to answer with.
    """
    if not context["nextFlag"] and not context["exactMatch"]:
        return context["origOid"], tag, context["errorStatus"]

    record = _options(value, "=")
    port = record["port"]
    if record["role"] == "state":
        _states.setdefault(port, int(record["value"]))

    if context["setFlag"]:
        if record["role"] != "control":
            return context["origOid"], tag, context["errorStatus"]
        written = int(context["origValue"])
        if written == _settings["on"]:
            _states[port] = _settings["state_on"]
        elif written == _settings["off"]:
            _states[port] = _settings["state_off"]
        return oid, tag, context["origValue"]

    state = _states.get(port)
    if record["role"] == "state":
        return oid, tag, state if state is not None else int(record["value"])
    if state is None:
        return oid, tag, int(record["value"])
    command = "on" if state == _settings["state_on"] else "off"
    return oid, tag, _settings[command]


def shutdown(**context: Any) -> None:
    """
    Forget every outlet state.

    :param context: the snmpsim context, which is not read.
    """
    _states.clear()
