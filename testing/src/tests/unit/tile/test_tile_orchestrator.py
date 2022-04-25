# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tile orchestrator."""
from __future__ import annotations

import contextlib
import logging
import unittest.mock
from collections import defaultdict
from typing import Any, ContextManager, Mapping, Optional, Tuple, Union, cast

import pytest
import pytest_mock
from _pytest.fixtures import SubRequest
from ska_tango_base.control_model import CommunicationStatus, PowerState

from ska_low_mccs.tile.tile_orchestrator import (
    StateStimulusTupleType,
    StateTupleType,
    Stimulus,
    TileOrchestrator,
)


class TestTileOrchestrator:
    """Class for testing the tile orchestrator."""

    @pytest.fixture(scope="session")
    def rules(
        self: TestTileOrchestrator,
    ) -> Mapping[StateStimulusTupleType, list[str]]:
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
        rules_table: dict[StateStimulusTupleType, list[str]] = {}
        for state, actions in TileOrchestrator._load_rules().items():
            if len(state) == 2:
                rules_table[
                    (
                        Stimulus[state[0]],
                        CommunicationStatus[state[1]],
                    )
                ] = actions
            elif len(state) == 4:
                rules_table[
                    (
                        Stimulus[state[0]],
                        CommunicationStatus[state[1]],
                        state[2],
                        PowerState[state[3]],
                    )
                ] = actions
            else:
                rules_table[
                    (
                        Stimulus[state[0]],
                        CommunicationStatus[state[1]],
                        state[2],
                        PowerState[state[3]],
                        CommunicationStatus[state[4]],
                    )
                ] = actions

        return rules_table

    @pytest.fixture(scope="session")
    def checks(
        self: TestTileOrchestrator,
    ) -> Mapping[
        str,
        Tuple[
            Mapping[str, Any],
            Mapping[str, list[Any]],
            Optional[ContextManager],
        ],
    ]:
        """
        Return a static dictionary of orchestrator action checks.

        The dictionary keys are names of actions that the orchestrator
        can takes. The values are checks we can performs to satisfy
        ourselves that the action was taken. Each check is a tuple of
        two dictionaries. The first dictionary specifies how we expect
        the state of the orchestrator to change. The second dictionary
        specifies how we expect the orchestrator to have called its
        callbacks.

        The :py:meth:`.actions` fixture specifies what action should be
        taken when a given stimulus arrives when the orchestrator is
        in a given status. Thus, the values of that dictionary can be
        used as keys of this one.

        :return: a static dictionary of choreography action checks.
        """
        return {
            "raise_cannot_turn_off_on_when_offline": (
                {},
                {},
                pytest.raises(
                    ConnectionError,
                    match="TPM cannot be turned off / on when not online.",
                ),
            ),
            "report_communication_disabled": (
                {},
                {"communication_status_changed": [CommunicationStatus.DISABLED]},
                None,
            ),
            "report_communication_not_established": (
                {},
                {"communication_status_changed": [CommunicationStatus.NOT_ESTABLISHED]},
                None,
            ),
            "report_communication_established": (
                {},
                {"communication_status_changed": [CommunicationStatus.ESTABLISHED]},
                None,
            ),
            "report_tpm_off": (
                {"tpm_power_state": PowerState.OFF},
                {"component_power_state_changed": [{"power_state": PowerState.OFF}]},
                None,
            ),
            "report_tpm_on": (
                {"tpm_power_state": PowerState.ON},
                {"component_power_state_changed": [{"power_state": PowerState.ON}]},
                None,
            ),
            "report_tpm_no_power_supply": (
                {"tpm_power_state": PowerState.NO_SUPPLY},
                {"component_power_state_changed": [{"power_state": PowerState.OFF}]},
                None,
            ),
            "report_tpm_power_unknown": (
                {"tpm_power_state": PowerState.UNKNOWN},
                {
                    "component_power_state_changed": [
                        {"power_state": PowerState.UNKNOWN}
                    ]
                },
                None,
            ),
            "set_desired_off": ({"operator_desire": False}, {}, None),
            "set_desired_on": ({"operator_desire": True}, {}, None),
            "set_no_desire": ({"operator_desire": None}, {}, None),
            "set_subrack_communication_established": (
                {"subrack_communication_status": CommunicationStatus.ESTABLISHED},
                {},
                None,
            ),
            "set_subrack_communication_not_established": (
                {"subrack_communication_status": CommunicationStatus.NOT_ESTABLISHED},
                {},
                None,
            ),
            "set_tpm_communication_established": (
                {"tpm_communication_status": CommunicationStatus.ESTABLISHED},
                {},
                None,
            ),
            "set_tpm_communication_not_established": (
                {"tpm_communication_status": CommunicationStatus.NOT_ESTABLISHED},
                {},
                None,
            ),
            "start_communicating_with_subrack": (
                {},
                {"start_communicating_with_subrack": []},
                None,
            ),
            "stop_communicating_with_subrack": (
                {"subrack_communication_status": CommunicationStatus.DISABLED},
                {"stop_communicating_with_subrack": []},
                None,
            ),
            "start_communicating_with_tpm": (
                {},
                {"start_communicating_with_tpm": []},
                None,
            ),
            "stop_communicating_with_tpm": (
                {"tpm_communication_status": CommunicationStatus.DISABLED},
                {"stop_communicating_with_tpm": []},
                None,
            ),
            "turn_tpm_off": ({}, {"turn_tpm_off": []}, None),
            "turn_tpm_on": ({}, {"turn_tpm_on": []}, None),
        }

    @pytest.fixture()
    def callbacks(
        self: TestTileOrchestrator,
        mocker: pytest_mock.MockerFixture,
    ) -> Mapping[str, unittest.mock.Mock]:
        """
        Return a dictionary of callbacks, keyed by an arbitrary name.

        :param mocker: fixture that wraps unittest.mock

        :return: a dictionary of callbacks
        """
        return defaultdict(mocker.Mock)

    @pytest.fixture(
        scope="session",
        params=[
            (CommunicationStatus.DISABLED,),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.NO_SUPPLY,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                True,
                PowerState.NO_SUPPLY,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.NO_SUPPLY,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                True,
                PowerState.NO_SUPPLY,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.OFF,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                True,
                PowerState.OFF,
            ),
            (CommunicationStatus.ESTABLISHED, None, PowerState.OFF),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.ON,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.ON,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.ON,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.ON,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.NOT_ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                None,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                False,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.DISABLED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.NOT_ESTABLISHED,
            ),
            (
                CommunicationStatus.ESTABLISHED,
                True,
                PowerState.UNKNOWN,
                CommunicationStatus.ESTABLISHED,
            ),
        ],
        ids=[
            "DISABLED",
            "NOT_ESTABLISHED_NO_SUPPLY",
            "NOT_ESTABLISHED_DESIRED_ON_NO_SUPPLY",
            "ESTABLISHED_NO_SUPPLY",
            "ESTABLISHED_DESIRED_ON_NO_SUPPLY",
            "NOT_ESTABLISHED_OFF",
            "NOT_ESTABLISHED_DESIRED_ON_OFF",
            "ESTABLISHED_OFF",
            "NOT_ESTABLISHED_ON_DISABLED",
            "NOT_ESTABLISHED_ON_NOT_ESTABLISHED",
            "NOT_ESTABLISHED_ON_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_OFF_ON_DISABLED",
            "NOT_ESTABLISHED_DESIRED_OFF_ON_NOT_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_OFF_ON_ESTABLISHED",
            "ESTABLISHED_ON_DISABLED",
            "ESTABLISHED_ON_NOT_ESTABLISHED",
            "ESTABLISHED_ON_ESTABLISHED",
            "NOT_ESTABLISHED_UNKNOWN_DISABLED",
            "NOT_ESTABLISHED_UNKNOWN_NOT_ESTABLISHED",
            "NOT_ESTABLISHED_UNKNOWN_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_OFF_UNKNOWN_DISABLED",
            "NOT_ESTABLISHED_DESIRED_OFF_UNKNOWN_NOT_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_OFF_UNKNOWN_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_ON_UNKNOWN_DISABLED",
            "NOT_ESTABLISHED_DESIRED_ON_UNKNOWN_NOT_ESTABLISHED",
            "NOT_ESTABLISHED_DESIRED_ON_UNKNOWN_ESTABLISHED",
            "ESTABLISHED_UNKNOWN_DISABLED",
            "ESTABLISHED_UNKNOWN_NOT_ESTABLISHED",
            "ESTABLISHED_UNKNOWN_ESTABLISHED",
            "ESTABLISHED_DESIRED_OFF_UNKNOWN_DISABLED",
            "ESTABLISHED_DESIRED_OFF_UNKNOWN_NOT_ESTABLISHED",
            "ESTABLISHED_DESIRED_OFF_UNKNOWN_ESTABLISHED",
            "ESTABLISHED_DESIRED_ON_UNKNOWN_DISABLED",
            "ESTABLISHED_DESIRED_ON_UNKNOWN_NOT_ESTABLISHED",
            "ESTABLISHED_DESIRED_ON_UNKNOWN_ESTABLISHED",
        ],
    )
    def state(
        self: TestTileOrchestrator, request: SubRequest
    ) -> Union[
        Tuple[CommunicationStatus],
        Tuple[
            CommunicationStatus,
            PowerState,
            CommunicationStatus,
            Optional[bool],
        ],
    ]:
        """
        Return an orchestrator state.

        The state is represented as a tuple containing some of:

        * what the operator desires the state of the orchestrator to
          be;
        * status of communication with the subrack
        * power mode of the subrack
        * whether the TPM is on (or None if unknown)
        * status of communication with the TPM

        :param request: A pytest object giving access to the requesting
            test context.

        :return: a summary of the state of the orchestrator
            (parametrized to return every possible value)
        """
        return request.param

    @pytest.fixture()
    def tile_orchestrator(
        self: TestTileOrchestrator,
        callbacks: Mapping[str, unittest.mock.Mock],
        logger: logging.Logger,
        state: StateTupleType,
    ) -> TileOrchestrator:
        """
        Return the tile orchestrator under test.

        :param callbacks: a dictionary of mocks to be used as callbacks.
        :param logger: a logger for the orchestrator.
        :param state: the initial state of the orchestrator.

        :return: the tile orchestrator under test.
        """
        return TileOrchestrator(
            callbacks["start_communicating_with_subrack"],
            callbacks["stop_communicating_with_subrack"],
            callbacks["start_communicating_with_tpm"],
            callbacks["stop_communicating_with_tpm"],
            callbacks["turn_tpm_off"],
            callbacks["turn_tpm_on"],
            callbacks["communication_status_changed"],
            callbacks["component_power_state_changed"],
            logger,
            _initial_state=state,
        )

    @pytest.fixture(scope="session", params=list(Stimulus), ids=lambda s: s.name)
    def stimulus(self: TestTileOrchestrator, request: SubRequest) -> Stimulus:
        """
        Return the name of a orchestrator stimulus.

        That is, any event in the environment that the orchestrator
        needs to act upon.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the name of a orchestrator stimulus
        """
        return request.param

    @pytest.fixture(scope="session")
    def check(
        self: TestTileOrchestrator,
        rules: Mapping[StateStimulusTupleType, str],
        checks: Mapping[
            str,
            Tuple[
                Mapping[str, Any],
                Mapping[str, list[Any]],
                Optional[ContextManager],
            ],
        ],
        state: StateTupleType,
        stimulus: Stimulus,
    ) -> Optional[
        Tuple[
            Mapping[str, Any],
            Mapping[str, list[Any]],
            Optional[ContextManager],
        ]
    ]:
        """
        Return checks to be performed as part of this test.

        These checks will confirm that the orchestrator took the right
        action when presented with a given stimulus when in a given
        state.

        The returned value is either None (signifying that the
        orchestrator does not know how to respond to the given stimulus
        in the given state), or a tuple of two dictionaries. The first
        dictionary specifies how we expect the state of the
        orchestrator to change. The second dictionary specifies how we
        expect the orchestrator to have called its callbacks.

        :raises KeyError: if this test doesn't know how to check that the
            orchestrator has taken the correct action.

        :param rules: a static dictionary of orchestrator rules.
        :param checks: a static dictionary of choreography action
            checks.
        :param state: the initial state of the tile orchestrator
        :param stimulus: a stimulus received by the tile orchestrator

        :return: the checks to be performed.
        """
        changed: dict[str, Any] = {}
        called: dict[str, list[Any]] = {}
        context: Optional[ContextManager] = None

        actions = rules[cast(StateStimulusTupleType, (stimulus,) + state)]
        for action in actions:
            if action not in checks:
                raise KeyError(f"Test does not know how to handle action {action}.")

            (this_changed, this_called, this_context) = checks[action]
            changed.update(this_changed)
            called.update(this_called)
            if this_context is not None:
                context = this_context  # TODO: support multiple contexts?

        return (changed, called, context)

    def test_orchestrator_action(
        self: TestTileOrchestrator,
        tile_orchestrator: TileOrchestrator,
        callbacks: Mapping[str, unittest.mock.Mock],
        state: StateTupleType,
        stimulus: Stimulus,
        check: Tuple[
            Mapping[str, Any],
            Mapping[str, list[Any]],
            Optional[ContextManager],
        ],
    ) -> None:
        """
        Test orchestrator actions.

        This test is very highly parametrized. It will run once for each
        possible stimulus in each possible state. i.e. thousands of
        times.

        :param tile_orchestrator: the tile orchestrator under test.
        :param callbacks: the callbacks that the tile orchestrator will
            call
        :param state: the initial state of the tile orchestrator
        :param stimulus: a stimulus received by the tile orchestrator
        :param check: the checks to be performed in order to ascertain
            that the tile orchestrator took the right action in
            response to the stimulus.
        """

        def stimulate() -> None:
            """Apply the specified stimulus on the orchestrator."""
            {
                Stimulus.DESIRE_ONLINE: lambda tc: tc.desire_online(),
                Stimulus.DESIRE_OFFLINE: lambda tc: tc.desire_offline(),
                Stimulus.DESIRE_ON: lambda tc: tc.desire_on(),
                Stimulus.DESIRE_OFF: lambda tc: tc.desire_off(),
                Stimulus.SUBRACK_COMMS_NOT_ESTABLISHED: lambda tc: tc.update_subrack_communication_status(
                    CommunicationStatus.NOT_ESTABLISHED
                ),
                Stimulus.SUBRACK_COMMS_ESTABLISHED: lambda tc: tc.update_subrack_communication_status(
                    CommunicationStatus.ESTABLISHED
                ),
                Stimulus.SUBRACK_SAYS_TPM_UNKNOWN: lambda tc: tc.update_tpm_power_state(
                    PowerState.UNKNOWN
                ),
                Stimulus.SUBRACK_SAYS_TPM_NO_SUPPLY: lambda tc: tc.update_tpm_power_state(
                    PowerState.NO_SUPPLY
                ),
                Stimulus.SUBRACK_SAYS_TPM_OFF: lambda tc: tc.update_tpm_power_state(
                    PowerState.OFF
                ),
                Stimulus.SUBRACK_SAYS_TPM_ON: lambda tc: tc.update_tpm_power_state(
                    PowerState.ON
                ),
                Stimulus.TPM_COMMS_NOT_ESTABLISHED: lambda tc: tc.update_tpm_communication_status(
                    CommunicationStatus.NOT_ESTABLISHED
                ),
                Stimulus.TPM_COMMS_ESTABLISHED: lambda tc: tc.update_tpm_communication_status(
                    CommunicationStatus.ESTABLISHED
                ),
            }[stimulus](tile_orchestrator)

        def check_state(**expected_state_changes: Any) -> None:
            """
            Check that the state of the orchestrator is as expected.

            It is expected that the state will be exactly what it was
            before, except for the changes specified in the provided
            keyword arguments. For example,
            ``check_state(is_tpm_on=False)`` will check that the tile
            orchestrator thinks the TPM is not turned on, and that all
            other elements of the state are unchanged from what they
            were.

            :param expected_state_changes: keyword arguments that
                specify state values that should have changed.
            """
            assert (
                tile_orchestrator._subrack_communication_status
                == expected_state_changes.get("subrack_communication_status", state[0])
            )
            if len(state) > 1:
                assert tile_orchestrator._operator_desire == expected_state_changes.get(
                    "operator_desire", state[1]  # type: ignore[misc]
                )
            if len(state) > 2:
                assert tile_orchestrator._tpm_power_state == expected_state_changes.get(
                    "tpm_power_state", state[2]  # type: ignore[misc]
                )
            if len(state) > 3:
                assert (
                    tile_orchestrator._tpm_communication_status
                    == expected_state_changes.get(
                        "tpm_communication_status", state[3]  # type: ignore[misc]
                    )
                )

        def check_callbacks(**expected_args: list[Any]) -> None:
            """
            Check that callbacks have been called as expected.

            The expectation is that the callbacks specified in the
            provided keyword arguments will have been called with the
            given positional arguments, and that all other callbacks
            will not have been called. For example,
            ``check_callbacks(component_fault=[True])`` will check that
            the tile orchestrator has called its component fault
            callback with the single positional argument ``True``.
            (Keyword arguments are not supported because to date we
            don't ever call callbacks with keyword arguments.)

            :param expected_args: keyword arguments that specify
                positional arguments for each callback that is expected
                to have been called.
            """
            for name in callbacks:
                if name in expected_args:
                    callbacks[name].assert_called_once_with(*(expected_args[name]))
                else:
                    callbacks[name].assert_not_called()

        changed: Mapping[str, Any]  # for the type checker
        called: Mapping[str, list[Any]]  # for the type checker
        context: Optional[ContextManager]
        (changed, called, context) = check

        # Finally! It's time to test.
        with context or contextlib.nullcontext():
            stimulate()
        check_state(**changed)
        check_callbacks(**called)
