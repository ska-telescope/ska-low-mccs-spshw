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
            msg_uid: str,
            notifications: bool,
            respond_to_fqdn: str,
            callback: str,
        ):
            """
            Message constructor.

            :param command: Tango command
            :param json_args: JSON encoded arguments to send to the command
            :param msg_uid: The message's unique identifier
            :param notifications: Does the client require push notifications?
            :param respond_to_fqdn: Response message FQDN
            :param callback: The callback (command) to call when command is complete
            """
            self.command = command
            self.json_args = json_args
            self.msg_uid = msg_uid
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
        self._msg_queue = SimpleQueue()
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
            self._qdebug("msgQRunning")
            while not self._terminate:
                self._check_msg_queue()

    def _notify_listener(self, command, progress):
        """
        Abstract method that requires implementation by derived concrete
        class for specific notifications.

        :param command: The command that needs a push notification
        :param progress: The notification to send to any subscribed listeners
        """
        self._qdebug("Error(_notify_listener)")
        self._logger.error("Derived class should implement _notify_listener()")

    def _execute_msg(self, msg):
        """
        Execute message from the message queue.

        :param msg: The message to execute
        """
        try:
            # Check we have a device to respond to before executing a command
            response_device = None
            if msg.respond_to_fqdn:
                try:
                    response_device = tango.DeviceProxy(msg.respond_to_fqdn)
                except DevFailed:
                    self._qdebug(f"Response device {msg.respond_to_fqdn} not found")
                    self._notify_listener(msg.command, ResultCode.UNKNOWN)
                    return

            self._logger.info(f"_execute_msg{msg.msg_uid}")
            self._qdebug(f"Exe({msg.msg_uid})")
            command = self._target.get_command_object(msg.command)
            if command:
                if msg.notifications:
                    self._qdebug(f"^({msg.msg_uid})")
                    self._notify_listener(msg.command, ResultCode.STARTED)

                # Incorporate FQDN and callback into command args dictionary
                # Add to kwargs and deal with the case if it's not a JSON encoded string
                try:
                    kwargs = json.loads(msg.json_args)
                except ValueError:
                    kwargs = {}
                except TypeError:
                    self._qdebug(f"TypeError({msg.command})")
                    self._logger.error(
                        f"TypeError: json_args for {msg.command} should be a JSON encoded string"
                    )
                    return
                kwargs["respond_to_fqdn"] = msg.respond_to_fqdn
                kwargs["callback"] = msg.callback
                json_string = json.dumps(kwargs)
                self._logger.info(
                    f"Calling {command} returning to fqdn={msg.respond_to_fqdn} "
                    + f"and callback={msg.callback}"
                )
                self._qdebug(f"msg kwargs({kwargs})")
                (result_code, message) = command(json_string)
                self._qdebug(f"Result({msg.msg_uid},rc={result_code.name})")
            else:
                raise KeyError
        except KeyError:
            message = (
                f"KeyError: Command {msg.command} not registered with this Tango device"
            )
            self._qdebug(f"KeyError({msg.command})")
            self._logger.error(message)
            return

        # Determine if we need to respond to a device
        if response_device:
            response = {
                "msg_obj": msg,
                "result_code": result_code,
                "message": message,
            }
            # Custom JSON encode required due to msg object embedded in our response
            json_string = json.dumps(response, default=lambda obj: obj.__dict__)
            self._qdebug(f'Reply to {response_device}.command_inout("{msg.callback}")')
            # Post response message
            response_device.command_inout(msg.callback, json_string)
            self._qdebug("Reply msg sent")
        else:
            self._qdebug("No reply required")
        self._qdebug(f"EndOfMsg({msg.msg_uid})")

    def _check_msg_queue(self):
        """
        Check to see if a message is waiting to be executed.
        Note: Timeout present to detect thread termination events.
        """
        try:
            msg = self._msg_queue.get(timeout=1.0)
        except Empty:
            return
        self._execute_msg(msg)

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
        msg_uid = f"{str(uuid4())}:{command}"
        msg = self.Message(
            command=command,
            json_args=json_args,
            msg_uid=msg_uid,
            notifications=notifications,
            respond_to_fqdn=respond_to_fqdn,
            callback=callback,
        )
        # rcltodo: protect with a try except for "Full" exception
        # rcltodo: Also limit the number of messages in a queue?
        #          Could be dangerous if many callbacks though - think!
        self._msg_queue.put(msg)
        self._qdebug(f"\nQ({msg.msg_uid})")
        status = f"Queued message {msg.msg_uid}"
        self._logger.info(status)
        return (ResultCode.QUEUED, status, msg.msg_uid)

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
