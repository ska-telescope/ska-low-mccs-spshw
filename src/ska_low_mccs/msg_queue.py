# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This module implements a message queue that executed message in it's own
thread.
"""
import threading
import json
from json import JSONEncoder
from tango import EnsureOmniThread, DeviceProxy
from queue import Queue
from ska_tango_base.commands import ResultCode
import uuid


class MessageQueue(threading.Thread):
    """
    A class for managing a queue of messages and the serial execution of
    said messages in their own thread.

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
            argin: str,
            msg_uid: str,
            timeout: int,
            notifications: bool,
            respond_to_fqdn: str,
            callback: str,
        ):
            """
            Message constructor.

            :param command: Tango command
            :param argin: Optional argument to send to the command
            :param msg_uid: The message's unique identifier
            :param timeout: Length of time before message should be cancelled
            :param notifications: Does the client require push notifications?
            :param respond_to_fqdn: Response message FQDN
            :param callback: The callback (command) to call when command is complete
            """
            self.command = command
            self.argin = argin
            self.msg_uid = msg_uid
            self.timeout = timeout
            self.notifications = notifications
            self.respond_to_fqdn = respond_to_fqdn
            self.callback = callback

    class GenericObjectEncoder(JSONEncoder):
        """
        A custom encoder so we can serialise generic objects.
        """

        def default(self, obj):
            """
            Routine to return the object's dictionary.

            :param obj: the object to serialise
            :return: the object's dictionary
            :rtype: dict
            """
            return obj.__dict__

    def __init__(self, target, lock, logger=None):
        """
        Initialise a new MessageQueue object.

        :param target: the device that this queue acts upon.
        :param lock: queue debug lock
        :param logger: the logger to be used by this object.
        """
        threading.Thread.__init__(self)
        self._msg_queue = Queue()
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
            while True:
                if self._terminate:
                    break
                self._check_msg_queue()

    def _notify_listener(self, command, progress):
        """
        Abstract method that requires implementation by derived concrete
        class for specific notifications.

        :param command: The command that needs a push notification
        :param progress: The notification to send to any subscribed listeners
        :raises NotImplementedError: if a derived class doesn't implement this method
        """
        raise NotImplementedError

    def _execute_msg(self, msg):
        """
        Execute message from the message queue.

        :param msg: The message to execute
        """
        self._logger.info(f"_execute_msg{msg.msg_uid}")
        self._qdebug(f"Exe({msg.msg_uid})")
        try:
            command = self._target.get_command_object(msg.command)
            if command:
                if msg.notifications:
                    self._qdebug(f"^({msg.msg_uid})")
                    self._notify_listener(msg.command, ResultCode.STARTED)

                # Incorporate fqdn and callback into args dictionary
                # Add to argin and deal with the case if it's not a JSON encoded string
                try:
                    kwargs = json.loads(msg.argin)
                except ValueError:
                    kwargs = {}
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

        # Determine if a response message is required
        if msg.respond_to_fqdn:
            response = {
                "msg_obj": msg,
                "result_code": result_code,
                "message": message,
            }
            device = DeviceProxy(msg.respond_to_fqdn)
            self._qdebug(f'Reply to {device}.command_inout("{msg.callback}")')

            # Call device method to post a message
            json_string = json.dumps(response, cls=self.GenericObjectEncoder)
            device.command_inout(msg.callback, json_string)
            self._qdebug("Reply msg sent")
        else:
            self._qdebug("No reply required")
        self._qdebug(f"EndOfMsg({msg.msg_uid})")

    def _check_msg_queue(self):
        """
        Check to see if a message is waiting to be executed.

        Note: This method blocks if the message queue is empty
        """
        self._logger.info("Waiting for message to execute")
        msg = self._msg_queue.get()
        self._execute_msg(msg)

    def terminate_thread(self):
        """
        External call to gracefully terminate this thread.
        """
        self._terminate = True

    def send_message(
        self,
        command: str,
        argin: str = "",
        timeout: int = 60,
        notifications: bool = False,
        respond_to_fqdn: str = "",
        callback: str = "",
    ):
        """
        Add message to the Tango device queue with the option of using
        Tango push notifications to indicate message progress and
        completion to subscribed listeners.

        :param command: Command to add to Tango device's message queue
        :param argin: Optional argument to send to the command
        :param timeout: Maximum duration that client will wait for completion of command
        :param notifications: Client requirement for push notifications
            for command's result attribute
        :param respond_to_fqdn: Response message FQDN
        :param callback: Callback command to call call
        :type callback: str
        :return: A tuple containing a result code (QUEUED, ERROR),
            a message string indicating status and a message object
        :rtype: (ResultCode, str, Message)
        """
        msg_uid = f"{str(uuid.uuid4())}:{command}"
        msg = self.Message(
            command=command,
            argin=argin,
            msg_uid=msg_uid,
            timeout=timeout,
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
        argin: str = "",
        timeout: int = 60,
        notifications: bool = False,
    ):
        """
        Add message to the Tango device queue with the option of using
        Tango push notifications to indicate message progress and
        completion to subscribed listeners.

        :param command: Command to add to Tango device's message queue
        :param respond_to_fqdn: Response message FQDN
        :param callback: The callback (command) to call when command is complete
        :param argin: Optional argument to send to the command
        :param timeout: Maximum duration that client will wait for completion of command
        :param notifications: Client requirement for push notifications for
            command's result attribute
        :return: A tuple containing a result code (QUEUED, ERROR),
            a message object and a message string indicating status.
        :rtype: (ResultCode, Message, str)
        """
        return self.send_message(
            command=command,
            argin=argin,
            timeout=timeout,
            notifications=notifications,
            respond_to_fqdn=respond_to_fqdn,
            callback=callback,
        )
