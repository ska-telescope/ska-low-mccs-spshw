# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the Tile Simulator interface."""
from __future__ import annotations

import ast
import inspect
from collections.abc import ValuesView
from inspect import Parameter
from pathlib import Path
from types import FunctionType

import pytest
from ska_low_sps_tpm_api.tile import Tile as AavsTile
from ska_low_sps_tpm_api.tile import TileHealthMonitor

from ska_low_mccs_spshw.tile import TileSimulator
from ska_low_mccs_spshw.tile.tile_simulator import MockTpm

SIMULATOR_ONLY_METHODS = [
    "mock_on",
    "mock_off",
    "cleanup",
    "simulate_health_value",
    "_timed_thread",
    "_TileSimulator__is_connectable",  # mangled
    "evaluate_mcu_action",
]
METHODS_TO_OMIT = [
    "__init__",
    "_convert_ip_to_str",
]


def _build_flattened_api() -> dict[str, FunctionType]:
    """
    Build the combined AavsTile + TileHealthMonitor method dict.

    :returns: dict mapping method name to function object for all methods in
        AavsTile and TileHealthMonitor.
    """
    flattened: dict[str, FunctionType] = {}
    flattened.update(
        {
            k: v
            for k, v in TileHealthMonitor.__dict__.items()
            if isinstance(v, FunctionType)
        }
    )
    flattened.update(
        {k: v for k, v in AavsTile.__dict__.items() if isinstance(v, FunctionType)}
    )
    return flattened


_FLATTENED_API = _build_flattened_api()


def _build_cm_called_tile_methods() -> set[str]:
    """
    Extract tile API method names used by TileComponentManager.

    This parser walks the AST of ``tile_component_manager.py`` and records
    calls that match the shape ``self.tile.<method>(...)``.

    Why this exists:
    - The simulator contract we care about is MCCS behaviour, not full upstream
    API parity.
    - Building the requirement set from CM call sites makes the test enforce the
    methods MCCS actually depends on.
    - Using AST keeps this robust against comments/whitespace and avoids brittle
    regex-only parsing.

    Scope intentionally excluded from this extractor:
    - Property reads (e.g. ``self.tile.some_property``)
    - Subscript access (e.g. ``self.tile[...]``)
    - Nested attribute chains (e.g. ``self.tile.tpm_monitor.method()``)

    :return: unique method names called directly on ``self.tile``.
    """
    cm_path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "ska_low_mccs_spshw"
        / "tile"
        / "tile_component_manager.py"
    )
    cm_source = cm_path.read_text(encoding="utf-8")
    parsed = ast.parse(cm_source)

    called: set[str] = set()
    for node in ast.walk(parsed):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Attribute):
            continue
        if not isinstance(node.func.value.value, ast.Name):
            continue
        if node.func.value.value.id != "self":
            continue
        if node.func.value.attr != "tile":
            continue
        called.add(node.func.attr)

    return called


_CM_CALLED_TILE_METHODS = _build_cm_called_tile_methods()

# Keep only methods from the upstream Tile API; this test validates simulator
# parity/signatures for API methods that MCCS actually invokes.
_CM_REQUIRED_API_METHODS = sorted(
    method for method in _CM_CALLED_TILE_METHODS if method in _FLATTENED_API
)


def test_cm_derived_requirements_sanity() -> None:
    """Sanity-check method extraction used by test_api_method_is_simulated."""
    assert _CM_REQUIRED_API_METHODS, "No CM-derived API methods were extracted."
    assert "set_csp_download" in _CM_REQUIRED_API_METHODS
    # This is an upstream API utility method, but not called by CM directly.
    assert "set_pps_sampling" not in _CM_REQUIRED_API_METHODS


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


@pytest.mark.parametrize("method_name", _CM_REQUIRED_API_METHODS)
def test_api_method_is_simulated(method_name: str) -> None:
    """
    Test that each CM-required AavsTile / TileHealthMonitor method is implemented.

    The TileSimulator simulates ska_low_sps_tpm_api.Tile. For each upstream
    API method that TileComponentManager calls on ``self.tile``, this test
    verifies that an implementation exists either:

    1. Directly on ``TileSimulator`` (the method appears in its ``__dict__``).
    2. Via ``TileSimulator.__getattr__`` delegation to ``MockTpm`` (the method
       appears in ``MockTpm.__dict__``).

    For whichever class provides the implementation, the method signature
    (parameter names, defaults, and kinds) must match the AavsTile signature.

    :param method_name: name of the API method under test (injected by
        ``pytest.mark.parametrize``).
    """
    in_tile_simulator = method_name in TileSimulator.__dict__
    in_mock_tpm = method_name in MockTpm.__dict__

    if not in_tile_simulator and not in_mock_tpm:
        pytest.fail(
            f"'{method_name}' is in ska-low-sps-tpm-api but not implemented in "
            "TileSimulator or MockTpm.  Add it to TileSimulator (preferred) when "
            "its behaviour needs to be simulated."
        )

    api_method = _FLATTENED_API[method_name]
    sim_method = (
        TileSimulator.__dict__[method_name]
        if in_tile_simulator
        else MockTpm.__dict__[method_name]
    )

    api_params = inspect.signature(api_method).parameters.values()
    sim_params = inspect.signature(sim_method).parameters.values()

    if not check_method_parameters_match(sim_params, api_params):
        source = "TileSimulator" if in_tile_simulator else "MockTpm"
        pytest.fail(
            f"'{method_name}' signature in {source} does not match AavsTile:\n"
            f"  simulator : {list(inspect.signature(sim_method).parameters.keys())}\n"
            f"  AavsTile  : {list(inspect.signature(api_method).parameters.keys())}"
        )
