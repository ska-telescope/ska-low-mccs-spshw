# type: ignore
########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for the ska_low_mccs.message_queue module."""
import pytest
import threading
import time
import json

from ska_tango_base.commands import ResultCode
from ska_low_mccs.message_queue import MessageQueue

from testing.harness.mock import MockDeviceBuilder


class TestMessageQueue:
    """
    This class contains the tests for the
    :py:class:`ska_low_mccs.message_queue.MessageQueue` class.
    """

    @pytest.fixture()
    def device_to_load(self):
        """
        The tango_harness fixture gets its specification of what devices to launch from
        the device_to_load fixture, so we need to provide that fixture. Since we're only
        going to be using mock devices here, we can just set it to return None.

        :return: None
        """
        return None

    @pytest.fixture()
    def callback(self):
        """
        Fixturizing callback as it's used in more than one place.

        :return: Name of the callback method
        """
        return "CallbackCommand"

    @pytest.fixture()
    def response_device(self, callback):
        """
        Let's build a mock device with a callback command with the right name, which
        returns a (ResultCode, ...) tuple.

        :param callback: Simple fixture for the name of a callback method
        :type callback: callback fixture

        :return: Mocked device that behaves like a response device should
        """
        builder = MockDeviceBuilder()
        builder.add_result_command(callback, result_code=ResultCode.OK)
        return builder()

    @pytest.fixture()
    def initial_mocks(self, valid_fqdn, response_device):
        """
        One of the ways we can tell the Tango harness about mock devices is to implement
        this fixture. Here we tell the Tango harness that when asked for a proxy to the
        "valid FQDN", it should return our callback device.

        :param valid_fqdn: a valid FQDN to use for our response device
        :type valid_fqdn: valid_fqdn fixture
        :param response_device: a fixture for our response device
        :type response_device: response_device fixture

        :return: a dictionary of mocks, keyed by FQDN
        """
        return {valid_fqdn: response_device}

    @pytest.fixture()
    def test_command(self):
        """
        A fixture returning a dummy command string.

        :return: A dummy command string
        """
        return "ACommand"

    @pytest.fixture()
    def valid_fqdn(self):
        """
        A fixture returning a valid FQDN string.

        :return: a valid FQDN string
        """
        return "low-mccs/control/control"

    @pytest.fixture()
    def command_return_ok(self, mocker):
        """
        A fixture for an executed command that returns ResultCode.OK.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :return: A mocked executed command returning ResultCode.OK
        """
        return mocker.Mock(return_value=(ResultCode.OK, ""))

    @pytest.fixture
    def target_mock(self, mocker):
        """
        A fixture that returns a mocked target device.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :return: A target mock device
        """
        mock = mocker.Mock()
        mock.queue_debug = ""
        mock._heart_beat = 0
        return mock

    @pytest.fixture
    def message_queue(self, logger, target_mock):
        """
        A fixture that yields a created and started message queue and terminates it
        after each test.

        :param logger: the logger to be used by the object under test
        :param target_mock: fixture that mocks a target device
        :yields: A message queue object
        """
        lock = threading.Lock()
        message_queue = MessageQueue(target=target_mock, lock=lock, logger=logger)
        message_queue.start()
        yield message_queue
        message_queue.terminate_thread()
        # Ensure the message queue's event loop has terminated
        message_queue.join()

    @pytest.fixture
    def specialised_message_queue(self, logger, target_mock):
        """
        A fixture that yields a created and started specialised message queue and
        terminates it after each test.

        :param logger: the logger to be used by the object under test
        :param target_mock: fixture that mocks a target device
        :yields: A message queue object
        """

        class SpecialisedMessageQueue(MessageQueue):
            """Specialised message queue that implements ``notify listener``."""

            def _notify_listener(self, result_code, message_uid, status):
                """
                Concrete test implementation of abstract base class to notify listeners.

                :param result_code: Result code of the command being executed
                :type result_code: :py:class:`~ska_tango_base.commands.ResultCode`
                :param message_uid: The message uid that needs a push notification
                :type message_uid: str
                :param status: Status message
                :type status: str
                """
                self.notify = (result_code, message_uid, status)

        lock = threading.Lock()
        message_queue = SpecialisedMessageQueue(
            target=target_mock, lock=lock, logger=logger
        )
        message_queue.start()
        yield message_queue
        message_queue.terminate_thread()
        # Ensure the message queue's event loop has terminated
        message_queue.join()

    def test_send_message_with_supported_command(
        self, message_queue, mocker, target_mock, command_return_ok, test_command
    ):
        """
        Test that we can send a message.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)
        (_, message_uid, _) = message_queue.send_message(command=test_command)
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        message_args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(message_args)
        command_return_ok.assert_called_once_with(json_string)
        assert f"Result({message_uid},rc=OK)" in target_mock.queue_debug

    def test_send_message_with_unsupported_command(
        self, message_queue, mocker, target_mock, test_command
    ):
        """
        Test that we can handle a message with an unsupported command.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock(return_value=None)
        message_queue.send_message(command=test_command)
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        assert f"KeyError({test_command})" in target_mock.queue_debug

    def test_send_message_with_command_and_args(
        self, message_queue, mocker, target_mock, command_return_ok, test_command
    ):
        """
        Test that we can send a message with args.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)
        argin = {"Myarg1": 42, "Myarg2": "42"}
        json_string = json.dumps(argin)
        (_, message_uid, _) = message_queue.send_message(
            command=test_command, json_args=json_string
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        message_args = {"respond_to_fqdn": "", "callback": ""}
        combined_args = {**argin, **message_args}
        json_string = json.dumps(combined_args)
        command_return_ok.assert_called_once_with(json_string)
        assert f"Result({message_uid},rc=OK)" in target_mock.queue_debug

    def test_send_message_with_command_and_incorrect_args(
        self, message_queue, mocker, target_mock, command_return_ok, test_command
    ):
        """
        Test that we can send a message with incorrect args format.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)
        argin = {"Myarg1": 42, "Myarg2": "42"}
        message_queue.send_message(command=test_command, json_args=argin)
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        command_return_ok.assert_not_called()
        assert f"TypeError({test_command})" in target_mock.queue_debug

    def test_send_message_with_command_with_notifications(
        self,
        specialised_message_queue,
        mocker,
        target_mock,
        command_return_ok,
        test_command,
    ):
        """
        Test that we can send a message with notifications.

        :param specialised_message_queue: specialised message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)
        (_, message_uid, _) = specialised_message_queue.send_message(
            command=test_command, notifications=True
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        message_args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(message_args)
        assert specialised_message_queue.notify[0] == ResultCode.STARTED
        assert test_command in specialised_message_queue.notify[1]
        command_return_ok.assert_called_once_with(json_string)
        assert f"Result({message_uid},rc=OK)" in target_mock.queue_debug

    def test_send_message_with_command_with_no_notifications_src(
        self, message_queue, mocker, target_mock, test_command
    ):
        """
        Test that we can send a message with notifications (but without derived class
        implementation)

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param test_command: a test command to send to the message queue
        """
        target_mock.get_command_object = mocker.Mock()
        message_queue.send_message(command=test_command, notifications=True)
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        assert "Error(_notify_listener)" in target_mock.queue_debug
        time.sleep(0.1)  # Required to allow DUT thread to run
        # The message queue should terminate if caller asked for notifications but
        # doesn't implement _notify_listener method.
        assert not message_queue.is_alive()

    # If we want to use the tango harness, we need to ensure
    # that the tango_harness fixture actually gets called. Most of
    # our unit tests test a device, so they use the
    # device_under_test fixture, which calls the tango_harness
    # fixture. So we mostly don't need to worry about making sure it
    # is called. But in the rarer case where we aren't testing a
    # device but we still need our tango harness (e.g. for mock
    # devices), we need to explicitly call it.
    @pytest.mark.usefixtures("tango_harness")
    def test_send_message_with_command_and_response(
        self,
        message_queue,
        mocker,
        target_mock,
        command_return_ok,
        test_command,
        valid_fqdn,
        callback,
        response_device,
    ):
        """
        Test that we can send a message with response callback.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        :param callback: Name of the callback method
        :param valid_fqdn: a valid FQDN string
        :param response_device: fixture that mocks a response device
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)

        (_, message_uid, _) = message_queue.send_message_with_response(
            command=test_command,
            respond_to_fqdn=valid_fqdn,
            callback=callback,
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        message_args = {"respond_to_fqdn": valid_fqdn, "callback": callback}
        json_string = json.dumps(message_args)
        command_return_ok.assert_called_once_with(json_string)
        assert f"Result({message_uid},rc=OK)" in target_mock.queue_debug
        args = {
            "message_object": {
                "command": test_command,
                "json_args": "",
                "message_uid": message_uid,
                "notifications": False,
                "respond_to_fqdn": valid_fqdn,
                "callback": callback,
            },
            "result_code": 0,
            "status": "",
        }
        json_string = json.dumps(args)
        response_device.command_inout.assert_called_once_with(callback, json_string)
