# type: ignore
"""
This module contains pytest fixtures and other test setups for the ska_low_mccs unit
tests.
"""
import pytest
import time
import tango
import json

from ska_tango_base.commands import ResultCode


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all tests that use the
    ``tango_harness`` fixture, causing them to be sandboxed in their own process.

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
def mock_callback(mocker):
    """
    Fixture that returns a mock to use as a callback.

    :param mocker: fixture that wraps unittest.Mock
    :type mocker: :py:class:`pytest_mock.mocker`

    :return: a mock to pass as a callback
    :rtype: :py:class:`unittest.mock.Mock`
    """
    return mocker.Mock()


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
        """
        Mocker private class.
        """

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

    return _MockEventCallback()
