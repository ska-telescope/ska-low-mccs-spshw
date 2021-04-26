# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a message queue that executes messages (in a
serial fashion) in its own thread.
"""
import threading
import json
import tango
from uuid import uuid4
from tango import EnsureOmniThread, DevFailed
from queue import SimpleQueue, Empty
from ska_tango_base.commands import ResultCode


class MessageQueue(threading.Thread):
    """
    A class for managing a queue of messages and the serial execution of
    said messages in the queue's execution thread.

    A Tango device can use this message queue mechanism to run in a
    separate thread. This thread will monitor and execute messages
    (Tango commands) from the queue. Messages can be configured to push
    notifications back to a subscribed listener and also pass a response
    message to a specified device via a response FQDN and callback
    (command).
    """

    class Message:
        """
        A message that is inserted onto the message queue.
        """

        def __init__(
            self,
            command: str,
            json_args: str,
            message_uid: str,
            notifications: bool,
            respond_to_fqdn: str,
            callback: str,
        ):
            """
            Message constructor.

            :param command: Tango command
            :param json_args: JSON encoded arguments to send to the command
            :param message_uid: The message's unique identifier
            :param notifications: Does the client require push notifications?
            :param respond_to_fqdn: Response message FQDN
            :param callback: The callback (command) to call when command is complete
            """
            self.command = command
            self.json_args = json_args
            self.message_uid = message_uid
            self.notifications = notifications
            self.respond_to_fqdn = respond_to_fqdn
            self.callback = callback

    def __init__(self, target, lock, logger=None):
        """
        Initialise a new MessageQueue object.

        :param target: the device that this queue acts upon.
        :param lock: queue debug lock
        :param logger: the logger to be used by this object.
        """
        threading.Thread.__init__(self)
        self._message_queue = SimpleQueue()
        self._terminate = False
        self._target = target
        self._qdebuglock = lock
        self._logger = logger

    def _qdebug(self, message):
        """
        A method to push a message onto the queue debug attribute of the
        target device.

        :param message: message string to add to the queue debug attribute
        """
        with self._qdebuglock:
            self._target.queue_debug += f"{message}\n"

    def run(self):
        """
        Thread run method executing the message queue loop.
        """
        # https://pytango.readthedocs.io/en/stable/howto.html
        # #using-clients-with-multithreading
        with EnsureOmniThread():
            self._qdebug("MessageQueueRunning")
            while not self._terminate:
                self._target._heart_beat += 1
                self._check_message_queue()

    def _notify_listener(self, command, progress):
        """
        Abstract method that requires implementation by derived concrete
        class for specific notifications.

        :param command: The command that needs a push notification
        :param progress: The notification to send to any subscribed listeners
        """
        self._qdebug("Error(_notify_listener) Thread Terminated")
        self._logger.error(
            "Derived class should implement _notify_listener(). Thread terminated"
        )
        # Terminate the thread execution loop
        self._terminate = True

    def _execute_message(self, message):
        """
        Execute message from the message queue.

        :param message: The message to execute
        """
        response_device = None
        try:
            # Check we have a device to respond to before executing a command
            if message.respond_to_fqdn:
                try:
                    response_device = tango.DeviceProxy(message.respond_to_fqdn)
                except DevFailed:
                    self._qdebug(f"Response device {message.respond_to_fqdn} not found")
                    self._notify_listener(message.command, ResultCode.UNKNOWN)
                    return

            self._logger.debug(f"_execute_message {message.message_uid}")
            self._qdebug(f"Exe({message.message_uid})")
            command = self._target.get_command_object(message.command)
            if command:
                if message.notifications:
                    self._qdebug(f"^({message.message_uid})")
                    self._notify_listener(message.command, ResultCode.STARTED)

                # Incorporate FQDN and callback into command args dictionary
                # Add to kwargs and deal with the case if it's not a JSON encoded string
                try:
                    kwargs = json.loads(message.json_args)
                except ValueError:
                    kwargs = {}
                except TypeError:
                    self._qdebug(f"TypeError({message.command})")
                    self._logger.error(
                        f"TypeError: json_args for {message.command} should be a JSON encoded string"
                    )
                    return
                kwargs["respond_to_fqdn"] = message.respond_to_fqdn
                kwargs["callback"] = message.callback
                json_string = json.dumps(kwargs)
                payload = (
                    f'Calling "{command}" returning to fqdn={message.respond_to_fqdn} '
                    + f"and callback={message.callback}"
                )
                self._logger.debug(payload)
                self._qdebug(payload)
                self._qdebug(f"Message kwargs({kwargs})")
                (result_code, status) = command(json_string)
                payload = f"Result({message.message_uid},rc={result_code.name})"
                self._logger.debug(payload)
                self._qdebug(payload)
            else:
                raise KeyError
        except KeyError:
            status = f"KeyError: Command {message.command} not registered with this Tango device"
            self._qdebug(f"KeyError({message.command})")
            self._logger.error(status)
            return

        # Determine if we need to respond to a device
        if response_device:
            response = {
                "message_object": message,
                "result_code": result_code,
                "status": status,
            }
            # Custom JSON encode required due to message object embedded in our response
            json_string = json.dumps(response, default=lambda obj: obj.__dict__)
            self._qdebug(
                f'Reply to {response_device}.command_inout("{message.callback}")'
            )
            self._qdebug(f"json_string={json_string}")
            # Post response message
            (rc, stat) = response_device.command_inout(message.callback, json_string)
            self._qdebug(f"Reply message sent rc={rc},status={stat}")
        else:
            self._qdebug("No reply required")
        self._qdebug(f"EndOfMessage({message.message_uid})")

    def _check_message_queue(self):
        """
        Check to see if a message is waiting to be executed.

        Note: Timeout present to detect thread termination events.
        """
        try:
            message = self._message_queue.get(timeout=1.0)
        except Empty:
            return
        self._execute_message(message)

    def terminate_thread(self):
        """
        External call to gracefully terminate this thread.
        """
        self._terminate = True

    def send_message(
        self,
        command: str,
        json_args: str = "",
        notifications: bool = False,
        respond_to_fqdn: str = "",
        callback: str = "",
    ):
        """
        Add message to the Tango device queue with the option of using
        Tango push notifications to indicate message progress and
        completion to subscribed listeners.

        :param command: Command to add to Tango device's message queue
        :param json_args: JSON encoded arguments to send to the command
        :param notifications: Client requirement for push notifications
            for command's result attribute
        :param respond_to_fqdn: Response message FQDN
        :param callback: Callback command to call call
        :type callback: str
        :return: A tuple containing a result code (QUEUED, ERROR),
            a message string indicating status and a message object
        :rtype: (ResultCode, str, Message)
        """
        message_uid = f"{str(uuid4())}:{command}"
        message = self.Message(
            command=command,
            json_args=json_args,
            message_uid=message_uid,
            notifications=notifications,
            respond_to_fqdn=respond_to_fqdn,
            callback=callback,
        )
        # rcltodo: protect with a try except for "Full" exception
        # rcltodo: Also limit the number of messages in a queue?
        #          Could be dangerous if many callbacks though - think!
        self._message_queue.put(message)
        self._qdebug(f"\nQ({message.message_uid})")
        status = f"Queued message {message.message_uid}"
        self._logger.info(status)
        return (ResultCode.QUEUED, status, message.message_uid)

    def send_message_with_response(
        self,
        command: str,
        respond_to_fqdn: str,
        callback: str,
        json_args: str = "",
        notifications: bool = False,
    ):
        """
        Add message to the Tango device queue with the option of using
        Tango push notifications to indicate message progress and
        completion to subscribed listeners.

        :param command: Command to add to Tango device's message queue
        :param respond_to_fqdn: Response message FQDN
        :param callback: The callback (command) to call when command is complete
        :param json_args: JSON encoded arguments to send to the command
        :param notifications: Client requirement for push notifications for
            command's result attribute
        :return: A tuple containing a result code (QUEUED, ERROR),
            a message object and a message string indicating status.
        :rtype: (ResultCode, Message, str)
        """
        return self.send_message(
            command=command,
            json_args=json_args,
            notifications=notifications,
            respond_to_fqdn=respond_to_fqdn,
            callback=callback,
        )
