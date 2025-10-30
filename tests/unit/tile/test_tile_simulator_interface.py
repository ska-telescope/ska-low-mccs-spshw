# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the Tile Simulator interface."""
from __future__ import annotations

import inspect
from collections.abc import ValuesView
from inspect import Parameter
from types import FunctionType

import pytest
from ska_low_sps_tpm_api.tile import Tile as AavsTile
from ska_low_sps_tpm_api.tile import TileHealthMonitor

from ska_low_mccs_spshw.tile import TileSimulator

SIMULATOR_ONLY_METHODS = [
    "mock_on",
    "mock_off",
    "_timed_thread",
    "_TileSimulator__is_connectable",  # mangled
    "evaluate_mcu_action",
]
METHODS_TO_OMIT = [
    "__init__",
    "_convert_ip_to_str",
]


def check_method_parameters_match(
    param_list_1: ValuesView[Parameter], param_list_2: ValuesView[Parameter]
) -> bool:
    """
    Check that method parameters match.

    Check method:
     - name
     - default value
     - kind (POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, etc.)

    :param param_list_1: the parameter list of method 1
    :param param_list_2: the parameter list of method 2

    :return: True if the paramerter list match.

    """
    params1 = [(p.name, p.default, p.kind) for p in param_list_1]
    params2 = [(p.name, p.default, p.kind) for p in param_list_2]

    if params1 != params2:
        print(f"Mismatch:\n{params1}\n!=\n{params2}")
        return False
    return True


def test_interface() -> None:
    """
    Test that the TileSimulator interface is correct.

    The TileSimulator aims to mock the ska-low-sps-tpm-api.
    This test is to ensure that the methods are available
    and have the correct signatures.
    """
    # Omit select methods.
    methods_to_omit = set(SIMULATOR_ONLY_METHODS + METHODS_TO_OMIT)

    # Grab all methods of both classes.
    tile_simulator_methods_to_test = {
        x: y for x, y in TileSimulator.__dict__.items() if isinstance(y, FunctionType)
    }
    aavs_tile_methods = {
        x: y for x, y in AavsTile.__dict__.items() if isinstance(y, FunctionType)
    }
    tile_health_methods = {
        x: y
        for x, y in TileHealthMonitor.__dict__.items()
        if isinstance(y, FunctionType)
    }

    # The TileSimulator simulates a flat aavs.tile.
    flattened_aavs_tile = {}
    flattened_aavs_tile.update(tile_health_methods)
    flattened_aavs_tile.update(aavs_tile_methods)

    # Delete any ommited methods.
    for method_to_ommit in methods_to_omit:
        tile_simulator_methods_to_test.pop(method_to_ommit)

    # Loop through all methods and check existance and signatures.
    for tile_sim_method_name, tile_sim_method in tile_simulator_methods_to_test.items():
        print(f"checking {tile_sim_method_name} ...")
        if tile_sim_method_name in flattened_aavs_tile:
            aavs_tile_parameters = inspect.signature(
                flattened_aavs_tile[tile_sim_method_name]
            ).parameters.values()
            tile_simulator_parameters = inspect.signature(
                tile_sim_method
            ).parameters.values()
            if not check_method_parameters_match(
                tile_simulator_parameters, aavs_tile_parameters
            ):
                pytest.fail(f"{tile_sim_method_name} parameters do not match.")
        else:
            pytest.fail(f"{tile_sim_method_name} not in ska-low-sps-tpm-api tile")
