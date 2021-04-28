########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska_low_mccs.message_queue
module.
"""
import pytest
import threading
import time
import json

from tango import DevFailed

from ska_tango_base.commands import ResultCode
from ska_low_mccs.message_queue import MessageQueue


class TestMessageQueue:
    """
    This class contains the tests for the
    :py:class:`ska_low_mccs.message_queue.MessageQueue` class.
    """

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
    def invalid_fqdn(self):
        """
        A fixture returning an invalid FQDN string.

        :return: an invalid FQDN string
        """
        return "an/invalid/fqdn"

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

    @pytest.fixture()
    def mock_device_proxy_with_devfailed(self, mocker):
        """
        A fixture that monkey patches Tango's DeviceProxy and raises a
        DevFailed exception.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :return: A monkey patched Tango device proxy which raises a DevFailed exception
        """
        mock = mocker.patch("tango.DeviceProxy", side_effect=DevFailed())
        return mock

    @pytest.fixture()
    def device(self, mocker):
        """
        A fixture that mocks a device.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :return: A mocked device
        """
        return mocker.Mock()

    @pytest.fixture()
    def mock_device_proxy(self, mocker, device):
        """
        A fixture that monkey patches Tango's DeviceProxy.

        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param device: fixture that mocks a device
        :return: A monkey patched Tango device proxy
        """
        mock = mocker.patch("tango.DeviceProxy", return_value=device)
        return mock

    @pytest.fixture
    def message_queue(self, logger, target_mock):
        """
        A fixture that yields a created and started message queue and
        terminates it after each test.

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
        A fixture that yields a created and started specialised message
        queue and terminates it after each test.

        :param logger: the logger to be used by the object under test
        :param target_mock: fixture that mocks a target device
        :yields: A message queue object
        """

        class SpecialisedMessageQueue(MessageQueue):
            """
            Specialised message queue with a concrete implementation of
            notify listener.
            """

            def _notify_listener(self, status, message_uid):
                """
                Concrete test implementation of abstract base class to
                notify listeners.

                :param status: result code for this message uid
                :type status: :py:class:`~ska_tango_base.commands.ResultCode`
                :param message_uid: unique id for the message being executed
                :type message_uid: str
                """
                self.notify = (status, message_uid)

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
        (_, _, message_uid) = message_queue.send_message(command=test_command)
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
        (_, _, message_uid) = message_queue.send_message(
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
        (_, _, message_uid) = specialised_message_queue.send_message(
            command=test_command, notifications=True
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        target_mock.get_command_object.assert_called_once_with(test_command)
        message_args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(message_args)
        assert specialised_message_queue.notify == (ResultCode.STARTED, test_command)
        command_return_ok.assert_called_once_with(json_string)
        assert f"Result({message_uid},rc=OK)" in target_mock.queue_debug

    def test_send_message_with_command_with_no_notifications_src(
        self, message_queue, mocker, target_mock, test_command
    ):
        """
        Test that we can send a message with notifications (but without
        derived class implementation)

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

    def test_send_message_with_command_with_response(
        self,
        message_queue,
        mocker,
        target_mock,
        command_return_ok,
        test_command,
        valid_fqdn,
        mock_device_proxy,
        device,
    ):
        """
        Test that we can send a message with response callback.

        :param message_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param command_return_ok: fixture for command that return ResultCode.OK
        :param test_command: a test command to send to the message queue
        :param valid_fqdn: a valid FQDN string
        :param mock_device_proxy: monkey patched device proxy
        :param device: fixture that mocks a device
        """
        target_mock.get_command_object = mocker.Mock(return_value=command_return_ok)
        callback = "callback_command"
        (_, _, message_uid) = message_queue.send_message_with_response(
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
        mock_device_proxy.assert_called_once_with(valid_fqdn)
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
        device.command_inout.assert_called_once_with(callback, json_string)

    def test_send_message_with_command_with_incorrect_response_fqdn(
        self,
        specialised_message_queue,
        mocker,
        target_mock,
        test_command,
        invalid_fqdn,
        mock_device_proxy_with_devfailed,
    ):
        """
        Test that we can handle a message with an incorrect response
        FQDN.

        :param specialised_message_queue: specialised message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :param target_mock: fixture that mocks a target device
        :param test_command: a test command to send to the message queue
        :param invalid_fqdn: an invalid FQDN string
        :param mock_device_proxy_with_devfailed: monkey patched device proxy which raises DevFailed exception
        """
        target_mock.get_command_object = mocker.Mock(return_value=None)
        callback = "callback_command"
        specialised_message_queue.send_message_with_response(
            command=test_command,
            respond_to_fqdn=invalid_fqdn,
            callback=callback,
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        mock_device_proxy_with_devfailed.assert_called_once_with(invalid_fqdn)
        assert f"Response device {invalid_fqdn} not found" in target_mock.queue_debug
        assert specialised_message_queue.notify == (
            ResultCode.UNKNOWN,
            test_command
        )
