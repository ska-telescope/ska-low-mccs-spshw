# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the tel state component manager."""
from __future__ import annotations

from typing import Any, Union

import pytest
from _pytest.fixtures import SubRequest

from ska_low_mccs.tel_state import TelState, TelStateComponentManager


class TestTelState:
    """
    Class for testing commands common to the component and its component manager.

    Because the tel state component manager passes commands down to the
    tel state component, many commands are common. Here we test those
    common commands.
    """

    @pytest.fixture(
        params=[
            "tel_state",
            "tel_state_component_manager",
        ]
    )
    def tel_state(
        self: TestTelState,
        tel_state_component: TelState,
        tel_state_component_manager: TelStateComponentManager,
        request: SubRequest,
    ) -> Union[TelState, TelStateComponentManager]:
        """
        Return the tel state component class object under test.

        This is parametrised to return

        * a tel state component,

        * a tel state component manager,

        So any test that relies on this fixture will be run twice.

        :param tel_state_component: the tel state component to return
        :param tel_state_component_manager: the tel state component
            component manager to return
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the tile class object under test
        """
        if request.param == "tel_state":
            return tel_state_component
        if request.param == "tel_state_component_manager":
            tel_state_component_manager.start_communicating()
            return tel_state_component_manager
        raise ValueError("tel_state fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value", "write_value"),
        (
            ("elements_states", "", "elements states test string"),
            ("observations_states", "", "observations states test string"),
            ("algorithms", "", "algorithms test string"),
            ("algorithms_version", "", "algorithms version test string"),
        ),
    )
    def test_read_write_attribute(
        self: TestTelState,
        tel_state: Union[TelState, TelStateComponentManager],
        attribute_name: str,
        expected_value: Any,
        write_value: Any,
    ) -> None:
        """
        Test read-write attributes.

        Test that the attributes take certain known initial values, and
        that we can write new values.

        This is a weak test; over time we should find ways to more
        thoroughly test each of these independently.

        :param tel_state: the tel state component class object under
            test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :param write_value: the value to write to the attribute
        """
        assert getattr(tel_state, attribute_name) == expected_value
        setattr(tel_state, attribute_name, write_value)
        assert getattr(tel_state, attribute_name) == write_value
