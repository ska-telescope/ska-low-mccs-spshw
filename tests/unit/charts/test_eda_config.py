# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module checks the EDA config refers to real device attributes."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# from ska_low_mccs_daq.daq_receiver.daq_receiver_device import MccsDaqReceiver
from tango.server import Device

# from ska_low_mccs_spshw.station.station_device import SpsStation
# from ska_low_mccs_spshw.subrack.subrack_device import MccsSubrack
from ska_low_mccs_spshw.tile.tile_device import MccsTile

EDA_CONFIG_PATH = (
    Path(__file__).parents[3] / "charts/ska-low-mccs-spshw/data/eda-config.yaml"
)

# Attributes that exist on a running device but are not declared on the class:
# State and Status are built into Tango, and the long running command
# attributes are added by ska-tango-base when the device initialises.
RUNTIME_ATTRIBUTES = {
    "state",
    "status",
    "longrunningcommandresult",
    "longrunningcommandstatus",
    "longrunningcommandsinqueue",
    "longrunningcommandidsinqueue",
    "longrunningcommandinprogress",
    "longrunningcommandprogress",
    "lrcqueue",
    "lrcexecuting",
}


def eda_attributes_for_class(device_class: str) -> list[str]:
    """
    Return the attributes the EDA config archives for a device class.

    :param device_class: the Tango class name as it appears in the EDA config.

    :return: the attribute names configured for that class.
    """
    with EDA_CONFIG_PATH.open() as config_file:
        config = yaml.safe_load(config_file)
    return [
        name
        for entry in config["configuration"]
        if entry["class"] == device_class
        for name in entry["attributes"]
    ]


@pytest.mark.parametrize(
    "device_class",
    [MccsTile],
    ids=lambda device_class: device_class.__name__,
)
def test_eda_config_attributes_exist(device_class: type[Device]) -> None:
    """
    Test that every attribute in the EDA config exists on the device class.

    Tango attribute names are case-insensitive, so compare them lowercased.

    :param device_class: the Tango device class to check.
    """
    device_attributes = {
        name.lower() for name in device_class.TangoClassClass.attr_list
    } | RUNTIME_ATTRIBUTES
    missing = [
        name
        for name in eda_attributes_for_class(device_class.__name__)
        if name.lower() not in device_attributes
    ]
    assert not missing, (
        f"EDA config references attributes not on {device_class.__name__}: "
        f"{missing}"
    )


def test_eda_config_attributes():
    for name in eda_attributes_for_class("MccsTile"):
        print(name)

    assert "this" is "that"
