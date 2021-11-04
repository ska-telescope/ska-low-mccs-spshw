# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""This module contains the tests of the tile orchestrator."""
from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any, Mapping, Optional, Tuple
import unittest.mock

import pytest
import pytest_mock
from _pytest.fixtures import SubRequest

from ska_tango_base.control_model import PowerMode

from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.tile.tile_orchestrator import OperatorDesire, TileOrchestrator


class TestTileOrchestrator:
    """Class for testing the tile orchestrator."""

    @pytest.fixture(scope="session")
    def actions(
        self,
    ) -> Mapping[
        Tuple[
            OperatorDesire,
            CommunicationStatus,
            Optional[PowerMode],
            Optional[bool],
            CommunicationStatus,
            str,
        ],
        str,
    ]:
        """
        Return a static dictionary of orchestrator actions.

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
        # fmt: off
        return {
            (OperatorDesire.OFFLINE, CommunicationStatus.DISABLED, None, None, CommunicationStatus.DISABLED, "desire_online"): "start_communicating_with_subrack",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_communication_disabled"): "set_subrack_communication_disabled",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "subrack_communication_disabled"): "set_subrack_communication_disabled",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "subrack_communication_disabled"): "set_subrack_communication_disabled",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "subrack_communication_disabled"): "set_subrack_communication_disabled",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.DISABLED, "subrack_communication_disabled"): "set_subrack_communication_disabled",  # noqa: E501
            (OperatorDesire.OFFLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.ESTABLISHED, "tpm_communication_disabled"): "set_tpm_communication_disabled",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.NOT_ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_communication_not_established"): "do_nothing",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.NOT_ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_communication_established"): "set_subrack_communication_established",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, None, None, CommunicationStatus.DISABLED, "desire_offline"): "stop_communicating",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_power_is_on"): "report_subrack_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, None, None, CommunicationStatus.DISABLED, "subrack_power_is_unknown"): "report_subrack_unknown",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.UNKNOWN, None, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.UNKNOWN, None, CommunicationStatus.DISABLED, "desire_on"): "set_desired_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "desire_on"): "set_desired_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "desire_offline"): "stop_communicating",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "subrack_power_is_on"): "report_subrack_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "subrack_power_is_unknown"): "report_subrack_unknown",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "desire_offline"): "stop_communicating",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "tpm_power_is_off"): "report_tpm_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "tpm_power_is_on"): "report_tpm_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "desire_on"): "set_desired_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "desire_offline"): "stop_communicating",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "desire_off"): "do_nothing",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "desire_on"): "turn_tpm_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.DISABLED, "tpm_power_is_on"): "report_tpm_on",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, False, CommunicationStatus.ESTABLISHED, "tpm_communication_disabled"): "set_tpm_communication_disabled",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.DISABLED, "tpm_communication_not_established"): "set_tpm_communication_not_established",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.NOT_ESTABLISHED, "tpm_communication_established"): "set_tpm_communication_established",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.ESTABLISHED, "desire_off"): "turn_tpm_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.ESTABLISHED, "desire_offline"): "stop_communicating",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.ESTABLISHED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ONLINE, CommunicationStatus.ESTABLISHED, PowerMode.ON, True, CommunicationStatus.ESTABLISHED, "tpm_power_is_off"): "report_tpm_off",  # noqa: E501
            (OperatorDesire.ON, CommunicationStatus.ESTABLISHED, PowerMode.OFF, None, CommunicationStatus.DISABLED, "subrack_power_is_on"): "report_subrack_on_and_turn_tpm_on",  # noqa: E501
            (OperatorDesire.ON, CommunicationStatus.ESTABLISHED, PowerMode.ON, None, CommunicationStatus.DISABLED, "tpm_power_is_off"): "report_tpm_off_and_turn_tpm_on",  # noqa: E501
            (OperatorDesire.ON, CommunicationStatus.ESTABLISHED, PowerMode.UNKNOWN, None, CommunicationStatus.DISABLED, "subrack_power_is_off"): "report_subrack_off",  # noqa: E501
            (OperatorDesire.ON, CommunicationStatus.ESTABLISHED, PowerMode.UNKNOWN, None, CommunicationStatus.DISABLED, "subrack_power_is_on"): "report_subrack_on_and_turn_tpm_on",  # noqa: E501
        }
        # fmt: on

    @pytest.fixture(scope="session")
    def checks(self) -> Mapping[str, Tuple[Mapping[str, Any], Mapping[str, list[Any]]]]:
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
            "do_nothing": ({}, {}),
            "report_subrack_off": (
                {"subrack_power_mode": PowerMode.OFF, "is_tpm_on": None},
                {
                    "component_power_mode_changed": [PowerMode.OFF],
                    "communication_status_changed": [CommunicationStatus.ESTABLISHED],
                },
            ),
            "report_subrack_on": ({"subrack_power_mode": PowerMode.ON}, {}),
            "report_subrack_on_and_turn_tpm_on": (
                {
                    "subrack_power_mode": PowerMode.ON,
                    "operator_desire": OperatorDesire.ONLINE,
                },
                {"turn_tpm_on": []},
            ),
            "report_subrack_unknown": (
                {"subrack_power_mode": PowerMode.UNKNOWN},
                {"component_power_mode_changed": [PowerMode.UNKNOWN]},
            ),
            "report_tpm_off": (
                {"is_tpm_on": False},
                {
                    "component_power_mode_changed": [PowerMode.OFF],
                    "stop_communicating_with_tpm": [],
                },
            ),
            "report_tpm_off_and_turn_tpm_on": (
                {"is_tpm_on": False, "operator_desire": OperatorDesire.ONLINE},
                {
                    "component_power_mode_changed": [PowerMode.OFF],
                    "turn_tpm_on": [],
                },
            ),
            "report_tpm_on": (
                {"is_tpm_on": True},
                {
                    "start_communicating_with_tpm": [],
                    "component_power_mode_changed": [PowerMode.ON],
                },
            ),
            "set_desired_on": ({"operator_desire": OperatorDesire.ON}, {}),
            "set_subrack_communication_disabled": (
                {
                    "subrack_communication_status": CommunicationStatus.DISABLED,
                    "subrack_power_mode": None,
                    "is_tpm_on": None,
                },
                {},
            ),
            "set_subrack_communication_established": (
                {"subrack_communication_status": CommunicationStatus.ESTABLISHED},
                {"communication_status_changed": [CommunicationStatus.ESTABLISHED]},
            ),
            "set_tpm_communication_disabled": (
                {"tpm_communication_status": CommunicationStatus.DISABLED},
                {},
            ),
            "set_tpm_communication_not_established": (
                {"tpm_communication_status": CommunicationStatus.NOT_ESTABLISHED},
                {"communication_status_changed": [CommunicationStatus.NOT_ESTABLISHED]},
            ),
            "set_tpm_communication_established": (
                {"tpm_communication_status": CommunicationStatus.ESTABLISHED},
                {"communication_status_changed": [CommunicationStatus.ESTABLISHED]},
            ),
            "start_communicating_with_subrack": (
                {
                    "operator_desire": OperatorDesire.ONLINE,
                    "subrack_communication_status": CommunicationStatus.NOT_ESTABLISHED,
                },
                {
                    "communication_status_changed": [
                        CommunicationStatus.NOT_ESTABLISHED
                    ],
                    "start_communicating_with_subrack": [],
                },
            ),
            "stop_communicating": (
                {"operator_desire": OperatorDesire.OFFLINE},
                {
                    "communication_status_changed": [CommunicationStatus.DISABLED],
                    "component_power_mode_changed": [None],
                    "component_fault": [None],
                    "stop_communicating_with_tpm": [],
                    "stop_communicating_with_subrack": [],
                },
            ),
            "turn_tpm_off": (
                {"operator_desire": OperatorDesire.ONLINE},
                {"turn_tpm_off": []},
            ),
            "turn_tpm_on": (
                {"operator_desire": OperatorDesire.ONLINE},
                {"turn_tpm_on": []},
            ),
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

    @pytest.fixture(params=list(OperatorDesire))
    def operator_desire(
        self: TestTileOrchestrator, request: SubRequest
    ) -> OperatorDesire:
        """
        Return what state the operator desires the orchestrator to be in.

        For example, if the operator has called the On() command but the
        orchestrator has not yet managed to turn the TPM on, then the
        desired state is ON.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the state that the operator desires the orchestrator
            to be in.
        """
        return request.param

    @pytest.fixture(params=list(CommunicationStatus))
    def subrack_communication_status(
        self: TestTileOrchestrator, request: SubRequest
    ) -> CommunicationStatus:
        """
        Return the status of communication with the subrack.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the status of communication with the subrack.
        """
        return request.param

    @pytest.fixture(params=[None] + list(PowerMode))
    def subrack_power_mode(
        self: TestTileOrchestrator, request: SubRequest
    ) -> Optional[PowerMode]:
        """
        Return the power mode of the subrack, or None if not yet known.

        Note that PowerMode.UNKNOWN represents the case where the
        subrack device has reported that it does not know the power mode
        of the subrack. ``None`` represents the case where we have not
        yet asked the subrack device what its power mode is, or we have
        asked but the subrack has not yet responded.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the power mode of the subrack, or None if not yet
            known.
        """
        return request.param

    @pytest.fixture(params=[None, False, True])
    def is_tpm_on(self: TestTileOrchestrator, request: SubRequest) -> Optional[bool]:
        """
        Return whether the TPM is powered on, of None if unknown.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the status of communication with the subrack.
        """
        return request.param

    @pytest.fixture(params=list(CommunicationStatus))
    def tpm_communication_status(
        self: TestTileOrchestrator, request: SubRequest
    ) -> CommunicationStatus:
        """
        Return the status of communication with the TPM.

        This fixture is parametrized to return each possible value. So
        any test or fixture that uses this fixture will be run once for
        each value.

        :param request: A pytest object giving access to the requesting
            test context.

        :return: the status of communication with the TPM.
        """
        return request.param

    @pytest.fixture()
    def state(
        self: TestTileOrchestrator,
        operator_desire: OperatorDesire,
        subrack_communication_status: CommunicationStatus,
        subrack_power_mode: Optional[PowerMode],
        is_tpm_on: Optional[bool],
        tpm_communication_status: CommunicationStatus,
    ) -> Tuple[
        OperatorDesire,
        CommunicationStatus,
        Optional[PowerMode],
        Optional[bool],
        CommunicationStatus,
    ]:
        """
        Return a summary of the state of the orchestrator.

        The state is represented as a tuple containing:

        * what the operator desires the state of the orchestrator to
          be;
        * status of communication with the subrack
        * power mode of the subrack
        * whether the TPM is on (or None if unknown)
        * status of communication with the TPM

        Note that each element in this tuple is provided by a
        parametrized fixture. This fixture therefore returns the cross-
        product of all these parametrizations. So any test or fixture
        that sues this fixture will be run once for each possible state
        i.e. hundreds of times.

        :param operator_desire: what the operator desires the state of
            the orchestrator to be (parametrized to return every
            possible value)
        :param subrack_communication_status: status of communications
            with the subrack (parametrized to return every possible
            value)
        :param subrack_power_mode: power mode of the subrack, or None if
            not yet known (parametrized to return every possible
            value)
        :param is_tpm_on: whether the TPM is turned on, or None if not
            yet known (parametrized to return every possible value)
        :param tpm_communication_status: status of communications with
            the TPM (parametrized to return every possible value)

        :return: a summary of the state of the orchestrator
            (parametrized to return every possible value)
        """
        return (
            operator_desire,
            subrack_communication_status,
            subrack_power_mode,
            is_tpm_on,
            tpm_communication_status,
        )

    @pytest.fixture()
    def tile_orchestrator(
        self: TestTileOrchestrator,
        callbacks: Mapping[str, unittest.mock.Mock],
        logger: logging.Logger,
        state: Tuple[
            OperatorDesire,
            CommunicationStatus,
            Optional[PowerMode],
            Optional[bool],
            CommunicationStatus,
        ],
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
            callbacks["component_power_mode_changed"],
            callbacks["component_fault"],
            logger,
            _initial_state=state,
        )

    @pytest.fixture(
        params=[
            "desire_online",
            "desire_offline",
            "desire_on",
            "desire_off",
            "subrack_communication_disabled",
            "subrack_communication_not_established",
            "subrack_communication_established",
            "subrack_power_is_unknown",
            "subrack_power_is_off",
            "subrack_power_is_standby",
            "subrack_power_is_on",
            "tpm_communication_disabled",
            "tpm_communication_not_established",
            "tpm_communication_established",
            "tpm_power_is_off",
            "tpm_power_is_on",
        ]
    )
    def stimulus(self: TestTileOrchestrator, request: SubRequest) -> str:
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

    @pytest.fixture()
    def check(
        self: TestTileOrchestrator,
        actions: Mapping[
            Tuple[
                OperatorDesire,
                CommunicationStatus,
                Optional[PowerMode],
                Optional[bool],
                CommunicationStatus,
                str,
            ],
            str,
        ],
        checks: Mapping[str, Tuple[Mapping[str, Any], Mapping[str, list[Any]]]],
        state: Tuple[
            OperatorDesire,
            CommunicationStatus,
            Optional[PowerMode],
            Optional[bool],
            CommunicationStatus,
        ],
        stimulus: str,
    ) -> Optional[Tuple[Mapping[str, Any], Mapping[str, list[Any]]]]:
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

        :param actions: a static dictionary of orchestrator actions.
        :param checks: a static dictionary of choreography action
            checks.
        :param state: the initial state of the tile orchestrator
        :param stimulus: a stimulus received by the tile orchestrator

        :return: the checks to be performed.
        """
        action = actions.get(state + (stimulus,), None)
        if action is None:
            return None
        if action not in checks:
            raise KeyError(f"Test does not know how to handle action {action}.")
        return checks[action]

    def test_orchestrator_action(
        self: TestTileOrchestrator,
        tile_orchestrator: TileOrchestrator,
        callbacks: Mapping[str, unittest.mock.Mock],
        state: Tuple[
            OperatorDesire,
            CommunicationStatus,
            Optional[PowerMode],
            Optional[bool],
            CommunicationStatus,
        ],
        stimulus: str,
        check: Optional[Tuple[Mapping[str, Any], Mapping[str, list[Any]]]],
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
                "desire_online": lambda tc: tc.desire_online(),
                "desire_offline": lambda tc: tc.desire_offline(),
                "desire_on": lambda tc: tc.desire_on(),
                "desire_off": lambda tc: tc.desire_off(),
                "subrack_communication_disabled": lambda tc: tc.update_subrack_communication_status(
                    CommunicationStatus.DISABLED
                ),
                "subrack_communication_not_established": lambda tc: tc.update_subrack_communication_status(
                    CommunicationStatus.NOT_ESTABLISHED
                ),
                "subrack_communication_established": lambda tc: tc.update_subrack_communication_status(
                    CommunicationStatus.ESTABLISHED
                ),
                "subrack_power_is_unknown": lambda tc: tc.update_subrack_power_mode(
                    PowerMode.UNKNOWN
                ),
                "subrack_power_is_off": lambda tc: tc.update_subrack_power_mode(
                    PowerMode.OFF
                ),
                "subrack_power_is_standby": lambda tc: tc.update_subrack_power_mode(
                    PowerMode.STANDBY
                ),
                "subrack_power_is_on": lambda tc: tc.update_subrack_power_mode(
                    PowerMode.ON
                ),
                "tpm_communication_disabled": lambda tc: tc.update_tpm_communication_status(
                    CommunicationStatus.DISABLED
                ),
                "tpm_communication_not_established": lambda tc: tc.update_tpm_communication_status(
                    CommunicationStatus.NOT_ESTABLISHED
                ),
                "tpm_communication_established": lambda tc: tc.update_tpm_communication_status(
                    CommunicationStatus.ESTABLISHED
                ),
                "tpm_power_is_off": lambda tc: tc.update_tpm_power_mode(PowerMode.OFF),
                "tpm_power_is_on": lambda tc: tc.update_tpm_power_mode(PowerMode.ON),
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
            assert tile_orchestrator._operator_desire == expected_state_changes.get(
                "operator_desire", state[0]
            )
            assert (
                tile_orchestrator._subrack_communication_status
                == expected_state_changes.get("subrack_communication_status", state[1])
            )
            assert tile_orchestrator._subrack_power_mode == expected_state_changes.get(
                "subrack_power_mode", state[2]
            )
            assert tile_orchestrator._is_tpm_on == expected_state_changes.get(
                "is_tpm_on", state[3]
            )
            assert (
                tile_orchestrator._tpm_communication_status
                == expected_state_changes.get("tpm_communication_status", state[4])
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

        if check is None:
            with pytest.raises(KeyError):
                stimulate()
            pytest.xfail("Unhandled case")
        else:
            (changed, called) = check

            # Finally! It's time to test.
            stimulate()
            check_state(**changed)
            check_callbacks(**called)
