# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for the custum AttributeManagers."""
from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import ANY

import pytest
import tango

from ska_low_mccs_spshw.tile.attribute_managers import (
    AttributeManager,
    BoolAttributeManager,
)


@pytest.fixture(name="alarm_handle", scope="module")
def alarm_handle_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock to call for alarm handling.

    :return: a mock to call for alarm handling.
    """
    return unittest.mock.Mock()


@pytest.fixture(name="post_change_event_callback", scope="module")
def post_change_event_callback_fixture() -> unittest.mock.Mock:
    """
    Fixture that provides a mock to call for value change handling.

    :return: a mock to call for value change handling
    """
    return unittest.mock.Mock()


@pytest.fixture(name="attribute_manager")
def attribute_manager_fixture(
    post_change_event_callback: unittest.mock.Mock,
) -> AttributeManager:
    """
    Fixture returning a AttributeManager instance.

    :param post_change_event_callback: a fixture containing
        a mock to be called on change.

    :return: a AttributeManager instance.
    """
    return AttributeManager(post_change_event_callback)


@pytest.fixture(name="attribute_manager_with_converter")
def attribute_manager_with_converter_fixture(
    post_change_event_callback: unittest.mock.Mock,
) -> AttributeManager:
    """
    Fixture returning a AttributeManager instance with a converter.

    :param post_change_event_callback: a fixture containing
        a mock to be called on change.

    :return: a AttributeManager instance with a converter.
    """

    def _serialise_value(val: dict[str, Any] | tuple[str, str]) -> str:
        return json.dumps(val)

    return AttributeManager(post_change_event_callback, converter=_serialise_value)


@pytest.fixture(name="alarm_on_high_bool_attribute_manager")
def alarm_on_high_bool_attribute_manager_fixture(
    post_change_event_callback: unittest.mock.Mock, alarm_handle: unittest.mock.Mock
) -> BoolAttributeManager:
    """
    Fixture returning a BoolAttributeManager instance.

    :param post_change_event_callback: a fixture containing
        a mock to be called on change.
    :param alarm_handle: a fixture containing
        a mock to be called on alarm.

    :return: a BoolAttributeManager instance.
    """
    return BoolAttributeManager(
        post_change_event_callback, alarm_flag="HIGH", alarm_handler=alarm_handle
    )


# pylint: disable=too-few-public-methods
class TestAttributeManager:
    """Test the base `AttributeManager` behaviour."""

    def test_push_on_change(
        self: TestAttributeManager,
        attribute_manager: AttributeManager,
        attribute_manager_with_converter: AttributeManager,
        post_change_event_callback: unittest.mock.Mock,
    ) -> None:
        """
        Test that we only push on change.

        :param attribute_manager: an `AttributeManager` instance.
        :param attribute_manager_with_converter: an `AttributeManager`
            instance with a converter.
        :param post_change_event_callback: a fixture containing
            a mock to be called on change.
        """
        test_value: int = 2
        attribute_manager.update(test_value)
        post_change_event_callback.assert_called_once_with(
            test_value, ANY, tango.AttrQuality.ATTR_VALID
        )
        post_change_event_callback.reset_mock()
        attribute_manager.update(2)
        post_change_event_callback.assert_not_called()
        test_dictionary = {"foo": 1, "bar": 2}
        attribute_manager_with_converter.update(test_dictionary)

        post_change_event_callback.assert_called_once_with(
            json.dumps(test_dictionary), ANY, tango.AttrQuality.ATTR_VALID
        )
        post_change_event_callback.reset_mock()
        attribute_manager_with_converter.update(test_dictionary)
        post_change_event_callback.assert_not_called()


class TestBoolAttributeManager:
    """
    Test the custom BoolAttributeManager.

    pytango does not currently have a method for evaluating
    the alarm state of DevBooleans. This AttributeManager is
    to alow booleans to be evaluates in the device state.
    """

    def test_push_on_change(
        self: TestBoolAttributeManager,
        alarm_on_high_bool_attribute_manager: BoolAttributeManager,
        post_change_event_callback: unittest.mock.Mock,
    ) -> None:
        """
        Test that a `BoolAttributeManager` pushes on change only.

        :param alarm_on_high_bool_attribute_manager: a `BoolAttributeManager` instance.
        :param post_change_event_callback: a fixture containing
            a mock to be called on change.
        """
        valid_value: bool = False
        attribute_manager = alarm_on_high_bool_attribute_manager
        attribute_manager.update(valid_value)
        post_change_event_callback.assert_called_once_with(
            valid_value, ANY, tango.AttrQuality.ATTR_VALID
        )
        post_change_event_callback.reset_mock()
        attribute_manager.update(valid_value)
        post_change_event_callback.assert_not_called()

    def test_alarm_on_high(
        self: TestBoolAttributeManager,
        alarm_on_high_bool_attribute_manager: BoolAttributeManager,
        post_change_event_callback: unittest.mock.Mock,
        alarm_handle: unittest.mock.Mock,
    ) -> None:  #
        """
        Test that a `BoolAttributeManager` pushes on ALARM.

        :param alarm_on_high_bool_attribute_manager: a `BoolAttributeManager` instance.
        :param post_change_event_callback: a fixture containing
            a mock to be called on change.
        :param alarm_handle: a fixture containing
            a mock to be called on alarm.
        """
        alarming_value: bool = True
        attribute_manager = alarm_on_high_bool_attribute_manager
        alarm_handle.reset_mock()
        post_change_event_callback.reset_mock()
        attribute_manager.update(alarming_value)
        post_change_event_callback.assert_called_once_with(
            alarming_value, ANY, tango.AttrQuality.ATTR_ALARM
        )
        alarm_handle.assert_called_once()
