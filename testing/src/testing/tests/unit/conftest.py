# type: ignore
"""This module contains pytest-specific test harness for MCCS unit tests."""
import json
import time
from typing import Callable
import unittest

import pytest
import pytest_mock
import tango

from ska_tango_base.commands import ResultCode


def pytest_itemcollected(item):
    """
    Modify a test after it has been collected by pytest.

    This pytest hook implementation adds the "forked" custom mark to all
    tests that use the ``tango_harness`` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: :py:class:`pytest.Item`
    """
    if "tango_harness" in item.fixturenames:
        item.add_marker("forked")


@pytest.fixture()
def devices_to_load(device_to_load):
    """
    Fixture that provides specifications of devices to load.

    In this case, it maps the simpler single-device spec returned by the
    "device_to_load" fixture used in unit testing, onto the more
    general multi-device spec.

    :param device_to_load: fixture that provides a specification of a
        single device to load; used only in unit testing where tests
        will only ever stand up one device at a time.
    :type device_to_load: dict

    :return: specification of the devices (in this case, just one
        device) to load
    :rtype: dict
    """
    if device_to_load is None:
        return None

    device_spec = {
        "path": device_to_load["path"],
        "package": device_to_load["package"],
        "devices": [
            {
                "name": device_to_load["device"],
                "proxy": device_to_load["proxy"],
            }
        ],
    }
    if "patch" in device_to_load:
        device_spec["devices"][0]["patch"] = device_to_load["patch"]

    return device_spec


@pytest.fixture()
def mock_callback_factory(
    mocker: pytest_mock.mocker,
) -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns a new mock callback each time it is called.

    Use this fixture in tests that need more than one mock_callback. If
    your tests only needs a single mock callback, it is simpler to use
    the :py:func:`mock_callback` fixture.

    :param mocker: fixture that provides a mock

    :return: a factory that returns a new mock callback each time it is
        called.
    """
    return mocker.Mock


@pytest.fixture()
def mock_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock]
) -> unittest.mock.Mock:
    """
    Return a mock to be used as a callback.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock to pass as a callback
    """
    return mock_callback_factory()


@pytest.fixture()
def mock_event_callback(mocker):
    """
    Fixture that returns a mock for use as an event callback.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a mock to pass as an event callback
    :rtype: :py:class:`unittest.mock.Mock`
    """

    class _MockEventCallback(mocker.Mock):
        """Mocker private class."""

        def check_event_data(self, name, result):
            """
            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska_tango_base.commands.ResultCode`
            """
            # push_change_event isn't synchronous, because it has to go
            # through the 0MQ event system. So we have to sleep long enough
            # for the event to arrive
            time.sleep(0.2)

            self.assert_called_once()
            event_data = self.call_args[0][0].attr_value

            assert event_data.name.casefold() == name.casefold()
            if result is not None:
                assert event_data.value == result
                assert event_data.quality == tango.AttrQuality.ATTR_VALID
            self.reset_mock()

        def check_command_result(self, name, result):
            """
            Special callback check routine for commandResult. There should always be two
            entries for commandResult; the first should reset commandResult to
            ResultCode.UNKNOWN, the second should match the expected result passed into
            this routine.

            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska_tango_base.commands.ResultCode`
            """
            # push_change_event isn't synchronous, because it has to go
            # through the 0MQ event system. So we have to sleep long enough
            # for the event to arrive
            time.sleep(0.2)

            self.assert_called()
            assert len(self.mock_calls) == 2  # exactly two calls

            first_event_data = self.mock_calls[0][1][0].attr_value
            second_event_data = self.mock_calls[1][1][0].attr_value
            assert first_event_data.name.casefold() == name.casefold()
            assert second_event_data.name.casefold() == name.casefold()
            values = json.loads(first_event_data.value)
            assert values.get("result_code") == ResultCode.UNKNOWN
            assert first_event_data.quality == tango.AttrQuality.ATTR_VALID
            if result is not None:
                values = json.loads(second_event_data.value)
                assert values.get("result_code") == result
                assert second_event_data.quality == tango.AttrQuality.ATTR_VALID
            self.reset_mock()

        def check_queued_command_result(self, name, result):
            """
            Special callback check routine for commandResult. There should always be
            four entries for commandResult; UNKNOWN, QUEUED, STARTED and the expected
            result passed into this routine.

            :param name: name of the registered event
            :type name: str
            :param result: return code from the completed command
                If set to None, value and quaility checks are bypassed
            :type result: :py:class:`~ska_tango_base.commands.ResultCode`
            """
            # push_change_event isn't synchronous, because it has to go
            # through the 0MQ event system. So we have to sleep long enough
            # for the event to arrive
            time.sleep(0.2)

            self.assert_called()
            assert len(self.mock_calls) == 4  # exactly four calls

            lookup = [ResultCode.UNKNOWN, ResultCode.QUEUED, ResultCode.STARTED, result]
            for entry in range(4):
                event_data = self.mock_calls[entry][1][0].attr_value
                assert event_data.name.casefold() == name.casefold()
                values = json.loads(event_data.value)
                if lookup[entry] is not None:
                    assert values.get("result_code") == lookup[entry]
                    assert event_data.quality == tango.AttrQuality.ATTR_VALID
            self.reset_mock()

    return _MockEventCallback()


@pytest.fixture()
def communication_status_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for component manager communication status.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the communication status
        of a component manager changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_power_mode_changed_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for component power mode change.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that the power mode of its component has changed.
    """
    return mock_callback_factory()


@pytest.fixture()
def component_fault_callback(
    mock_callback_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for component fault.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the component manager
        detects that its component has faulted.
    """
    return mock_callback_factory()
