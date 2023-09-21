# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains the tests of the tile orchestration rules.

It contains tests of the logical correctness of the orchestration rules themselves.
For tests of the `TileOrchestrator` class, see `test_tile_orchestrator.py`.
"""
from __future__ import annotations

from typing import Mapping

import pytest

from ska_low_mccs_spshw.tile.tile_orchestrator import (
    StateStimulusTupleType,
    TileOrchestrator,
)


@pytest.fixture(scope="session", name="rules")
def rules_fixture() -> (
    Mapping[
        tuple[str, str]
        | tuple[str, str, bool | None, str]
        | tuple[str, str, bool | None, str, str],
        list[str],
    ]
):
    """
    Return a static dictionary of orchestrator rules.

    The dictionary keys are tuples that describe the current state
    of the orchestrator, together with the stimulus that has just
    occurred. Values are the name of an action that the
    orchestrator is expected to take in that situation.

    The :py:meth:`.checks` fixture specifies the checks we can
    perform in order to ascertain that the expected action has been
    taken. Thus, the values of this dictionary are keys of the
    ``checks`` dictionary.

    :return: a static dictionary of orchestrator actions
    """
    return TileOrchestrator._load_rules()


def test_orchestrator_ignores_external_stimuli_when_offline(
    rules: Mapping[StateStimulusTupleType, list[str]]
) -> None:
    """
    Test that the orchestration rules specify to ignore external stimuli when offline.

    This is a bedrock principle:
    when a device is offline, it ignores any external stimuli,
    such as updates from the subrack Tango device or from its TPM,
    and will only change its internal state in response to being put online.

    :param rules: the rules under test.
    """
    for state, actions in rules.items():
        stimulus = state[0]
        subrack_state = state[1]

        if subrack_state != "DISABLED":
            continue
        if stimulus in [
            "SUBRACK_COMMS_NOT_ESTABLISHED",
            "SUBRACK_COMMS_ESTABLISHED",
            "SUBRACK_SAYS_TPM_UNKNOWN",
            "SUBRACK_SAYS_TPM_NO_SUPPLY",
            "SUBRACK_SAYS_TPM_OFF",
            "SUBRACK_SAYS_TPM_ON",
            "TPM_COMMS_NOT_ESTABLISHED",
            "TPM_COMMS_ESTABLISHED",
        ]:
            assert not actions
