########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska_low_mccs.msg_queue module.
"""
import pytest
import threading
import time
import json

from tango import DevFailed
from unittest import mock

from ska_tango_base.commands import ResultCode
from ska_low_mccs.msg_queue import MessageQueue


class TestMessageQueue:
    """
    This class contains the tests for the
    :py:class:`ska_low_mccs.msg_queue.MessageQueue` class.
    """

    test_command = "ACommand"
    respond_to_fqdn = "low-mccs/control/control"

    @pytest.fixture
    def msg_queue(self, logger, mocker):
        """
        A fixture that yields a created and started message queue and
        terminates it after each test.

        :param logger: the logger to be used by the object under test
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :yields: A message queue object
        """
        self.target_mock = mocker.Mock()
        self.target_mock.queue_debug = ""
        lock = threading.Lock()
        msg_queue = MessageQueue(target=self.target_mock, lock=lock, logger=logger)
        msg_queue.start()
        yield msg_queue
        msg_queue.terminate_thread()
        # Ensure the message queue's event loop has terminated
        msg_queue.join()
        self.target_mock = None

    @pytest.fixture
    def specialised_msg_queue(self, logger, mocker):
        """
        A fixture that yields a created and started specialised message
        queue and terminates it after each test.

        :param logger: the logger to be used by the object under test
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        :yields: A message queue object
        """

        class SpecialisedMessageQueue(MessageQueue):
            """
            Specialised message queue with a concrete implementation of
            notify listener.
            """

            def _notify_listener(self, command, progress):
                """
                Concrete test implementation of abstract base class to
                notify listeners.

                :param command: The command that needs a push notification
                :param progress: The notification to send to any subscribed listeners
                """
                self.notify = (command, progress)

        self.target_mock = mocker.Mock()
        self.target_mock.queue_debug = ""
        lock = threading.Lock()
        msg_queue = SpecialisedMessageQueue(
            target=self.target_mock, lock=lock, logger=logger
        )
        msg_queue.start()
        yield msg_queue
        msg_queue.terminate_thread()
        # Ensure the message queue's event loop has terminated
        msg_queue.join()
        self.target_mock = None

    def test_send_msg_with_supported_command(self, msg_queue, mocker):
        """
        Test that we can send a message.

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        command_exe = mocker.Mock(return_value=(ResultCode.OK, ""))
        self.target_mock.get_command_object = mocker.Mock(return_value=command_exe)
        (_, _, msg_uid) = msg_queue.send_message(command=self.test_command)
        time.sleep(0.1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        msg_args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(msg_args)
        command_exe.assert_called_once_with(json_string)
        assert f"Result({msg_uid},rc=OK)" in self.target_mock.queue_debug

    def test_send_msg_with_unsupported_command(self, msg_queue, mocker):
        """
        Test that we can handle a message with an unsupported command.

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        self.target_mock.get_command_object = mocker.Mock(return_value=None)
        msg_queue.send_message(command=self.test_command)
        time.sleep(0.1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        assert f"KeyError({self.test_command})" in self.target_mock.queue_debug

    def test_send_msg_with_command_and_args(self, msg_queue, mocker):
        """
        Test that we can send a message with args.

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        command_exe = mocker.Mock(return_value=(ResultCode.OK, ""))
        self.target_mock.get_command_object = mocker.Mock(return_value=command_exe)
        argin = {"Myarg1": 42, "Myarg2": "42"}
        json_string = json.dumps(argin)
        (_, _, msg_uid) = msg_queue.send_message(
            command=self.test_command, json_args=json_string
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        msg_args = {"respond_to_fqdn": "", "callback": ""}
        combined_args = {**argin, **msg_args}
        json_string = json.dumps(combined_args)
        command_exe.assert_called_once_with(json_string)
        assert f"Result({msg_uid},rc=OK)" in self.target_mock.queue_debug

    def test_send_msg_with_command_and_incorrect_args(self, msg_queue, mocker):
        """
        Test that we can send a message with incorrect args format.

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        command_exe = mocker.Mock()
        self.target_mock.get_command_object = mocker.Mock(return_value=command_exe)
        argin = {"Myarg1": 42, "Myarg2": "42"}
        msg_queue.send_message(command=self.test_command, json_args=argin)
        time.sleep(0.1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        command_exe.assert_not_called()
        assert f"TypeError({self.test_command})" in self.target_mock.queue_debug

    def test_send_msg_with_command_with_notifications(
        self, specialised_msg_queue, mocker
    ):
        """
        Test that we can send a message with notifications.

        :param specialised_msg_queue: specialised message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        command_exe = mocker.Mock(return_value=(ResultCode.OK, ""))
        self.target_mock.get_command_object = mocker.Mock(return_value=command_exe)
        (_, _, msg_uid) = specialised_msg_queue.send_message(
            command=self.test_command, notifications=True
        )
        time.sleep(0.1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        msg_args = {"respond_to_fqdn": "", "callback": ""}
        json_string = json.dumps(msg_args)
        assert specialised_msg_queue.notify == (self.test_command, ResultCode.STARTED)
        command_exe.assert_called_once_with(json_string)
        assert f"Result({msg_uid},rc=OK)" in self.target_mock.queue_debug

    def test_send_msg_with_command_with_no_notifications_src(self, msg_queue, mocker):
        """
        Test that we can send a message with notifications (but without
        derived class implementation)

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        self.target_mock.get_command_object = mocker.Mock()
        msg_queue.send_message(command=self.test_command, notifications=True)
        time.sleep(1)  # Required to allow DUT thread to run
        self.target_mock.get_command_object.assert_called_once_with(self.test_command)
        assert "Error(_notify_listener)" in self.target_mock.queue_debug

    def test_send_msg_with_command_with_response(self, msg_queue, mocker):
        """
        Test that we can send a message with response callback.

        :param msg_queue: message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        with mock.patch("tango.DeviceProxy") as mock_device_proxy:
            command_exe = mocker.Mock(return_value=(ResultCode.OK, ""))
            self.target_mock.get_command_object = mocker.Mock(return_value=command_exe)
            device = mocker.Mock()
            mock_device_proxy.return_value = device
            callback = "callback_command"
            (_, _, msg_uid) = msg_queue.send_message_with_response(
                command=self.test_command,
                respond_to_fqdn=self.respond_to_fqdn,
                callback=callback,
            )
            time.sleep(0.1)  # Required to allow DUT thread to run
            self.target_mock.get_command_object.assert_called_once_with(
                self.test_command
            )
            msg_args = {"respond_to_fqdn": self.respond_to_fqdn, "callback": callback}
            json_string = json.dumps(msg_args)
            command_exe.assert_called_once_with(json_string)
            assert f"Result({msg_uid},rc=OK)" in self.target_mock.queue_debug
            mock_device_proxy.assert_called_once_with(self.respond_to_fqdn)
            args = {
                "msg_obj": {
                    "command": self.test_command,
                    "json_args": "",
                    "msg_uid": msg_uid,
                    "notifications": False,
                    "respond_to_fqdn": self.respond_to_fqdn,
                    "callback": callback,
                },
                "result_code": 0,
                "message": "",
            }
            json_string = json.dumps(args)
            device.command_inout.assert_called_once_with(callback, json_string)

    def test_send_msg_with_command_with_incorrect_response_fqdn(
        self, specialised_msg_queue, mocker
    ):
        """
        Test that we can handle a message with an incorrect response
        FQDN.

        :param specialised_msg_queue: specialised message queue fixture
        :param mocker: fixture that wraps the :py:mod:`unittest.mock` module
        """
        with mock.patch(
            "tango.DeviceProxy", side_effect=DevFailed()
        ) as mock_device_proxy:
            self.target_mock.get_command_object = mocker.Mock(return_value=None)
            incorrect_fqdn = "a/bad/fqdn"
            callback = "callback_command"
            specialised_msg_queue.send_message_with_response(
                command=self.test_command,
                respond_to_fqdn=incorrect_fqdn,
                callback=callback,
            )
            time.sleep(0.1)  # Required to allow DUT thread to run
            mock_device_proxy.assert_called_once_with(incorrect_fqdn)
            assert (
                f"Response device {incorrect_fqdn} not found"
                in self.target_mock.queue_debug
            )
            assert specialised_msg_queue.notify == (
                self.test_command,
                ResultCode.UNKNOWN,
            )
