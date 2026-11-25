#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Tests of the switch that selects the subrack implementation."""
from __future__ import annotations

import pytest

import ska_low_mccs_spshw
from ska_low_mccs_spshw import (
    SUBRACK_IMPLEMENTATION_ENV_VAR,
    MccsPrototypeSubrack,
    server_classes,
    subrack_class,
)
from ska_low_mccs_spshw.subrack import MccsSubrack as LegacyMccsSubrack


@pytest.mark.parametrize("implementation", [None, "legacy"])
def test_legacy_is_the_default(
    monkeypatch: pytest.MonkeyPatch, implementation: str | None
) -> None:
    """
    Test that the legacy subrack is served by default and with ``legacy``.

    :param monkeypatch: sets the environment variable.
    :param implementation: the value of the environment variable, or ``None``
        to leave it unset.
    """
    if implementation is None:
        monkeypatch.delenv(SUBRACK_IMPLEMENTATION_ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(SUBRACK_IMPLEMENTATION_ENV_VAR, implementation)

    assert subrack_class() is LegacyMccsSubrack
    assert ska_low_mccs_spshw.MccsSubrack is LegacyMccsSubrack


def test_prototype_is_a_fixed_mccs_subrack_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that ``prototype`` serves one fixed prototype class named ``MccsSubrack``.

    :param monkeypatch: sets the environment variable.
    """
    monkeypatch.setenv(SUBRACK_IMPLEMENTATION_ENV_VAR, "prototype")

    prototype = subrack_class()
    assert prototype.__name__ == "MccsSubrack"
    assert issubclass(prototype, MccsPrototypeSubrack)
    assert subrack_class() is prototype
    assert ska_low_mccs_spshw.MccsSubrack is prototype
    assert server_classes().count(prototype) == 1
    assert LegacyMccsSubrack not in server_classes()
    assert MccsPrototypeSubrack in server_classes()


def test_an_unknown_implementation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that an unknown value raises, rather than selecting the legacy subrack.

    :param monkeypatch: sets the environment variable.
    """
    monkeypatch.setenv(SUBRACK_IMPLEMENTATION_ENV_VAR, "prototpye")

    with pytest.raises(ValueError, match="prototpye"):
        subrack_class()
