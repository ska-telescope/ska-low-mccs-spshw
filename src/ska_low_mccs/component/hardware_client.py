# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
Abstract class to establish a simple connection to a remote hardware device (client).

Protocol is based on a set of commands and attributes (loosely related to
Tango commands and attributes). An attribute is a property which can be
read and optionally written. A command is an action performed by the client,
optionally using paramenters. Both commands and attribute requests always
return a response, in a form of a JSON encoded structure. This in turn
is translated to a dictionary and returned to the request initiator.

The client implements a fixed set of commands and attributes. An attribute
is read-only or read-write, in a fixed way.

Commands may be synchronous or asynchronous. Synchronous commands complete
the required operation and return in a short time (typ less than 1 second).
Asynchronous commands start a separate thread. All requests to the device
fail if the command is still active, except the "abort_command" command, which
aborts it and the "command_completed" command, which returns the completion
status as a Bool value.

Response dictionary for commands:
    * status: OK, ERROR, or STARTED (for async commands)
    * info: textual description of the command result/error
    * command: the command name
    * retvalue: returned value, if any

Attributes can be read and written. Write to a read-only attribute fails.
All attribute operations are synchronous.

Response dictionary for attributes:
    * status: OK, ERROR
    * info: textual description of the operation result/error
    * attribute: the attribute name
    * value: returned value, if any

Commands "list_commands" and "list_attributes" are always implemented, and
return a list of the available command/attribute names.
"""
import requests
import json


class HardwareClient:
    """
    An abstract client to establish a connection to hardware.

    This must be subclassed to establish the actual network protocol.
    """

    def __init__(self, ip_address, port=80):
        """
        Create a new instance.

        :param ip_address: IP address of server
        :type ip_address: str
        :param port: Port of server
        :type port: int
        """
        self._ip = ip_address
        self._port = port
        self._conn = None

    def connect(self):
        """
        Check if connected and establish a connection with the client. If this is not
        possible, returns None.

        None if no connection available, True if connection OK
        """
        pass

    def execute_command(self, command, parameters=""):
        """
        Execute the command.

        :param command: Name of command to be executed
        :type command: str
        :param parameters: Parameters of the command
        :type parameters: str
        :return: dictionary with execute_command result
        :rtype: dict
        """
        return {
            "status": "OK",
            "info": command + " completed OK",
            "command": command,
            "retvalue": "",
        }

    def get_attribute(self, attribute):
        """
        Get the attribute from the device.

        :param attribute: Name of attribute to get
        :type attribute: str

        :return: dictionary with get_attribute method result
        :rtype: dict
        """
        return {
            "status": "OK",
            "info": attribute + " completed OK",
            "attribute": attribute,
            "retvalue": "",
        }

    def set_attribute(self, attribute, value):
        """
        Set the attribute value.

        :param attribute: Name of attribute to set
        :type attribute: str
        :param value: value to set
        :type value: list or int or float

        :return: dictionary with set_attribute method result
        :rtype: dict
        """
        return {
            "status": "OK",
            "info": attribute + " completed OK",
            "attribute": attribute,
            "value": "",
        }


class WebHardwareClient(HardwareClient):
    """Implementation of the HardwareClient protocol using a web based interface."""

    def __init__(self, ip_address, port=80):
        """
        Create a new instance of the HardwareClient protocol to a html based
        HardwareServer device.

        :param ip_address: IP address of server
        :type ip_address: str
        :param port: Port of server
        :type port: int
        """
        super().__init__(ip_address, port)
        try:
            self._conn = requests.request(
                "GET",
                url=f"http://{self._ip}:{self._port}",
                timeout=2,
            )
        except requests.exceptions.RequestException:
            self._conn = None

    def connect(self):
        """
        Check if connected and establish a connection with the client.

        If this is not possible, returns within 2 seconds
        :return: return result of the connect method
        :rtype:bool
        """
        if self._conn is None:
            try:
                self._conn = requests.request(
                    "GET",
                    url=f"http://{self._ip}:{self._port}",
                    timeout=10,
                )
            except requests.exceptions.RequestException:
                self._conn = None
        return not (self._conn is None)

    def disconnect(self):
        """Disconnect from the client."""
        self._conn = None

    def execute_command(self, command, parameters=""):
        """
        Execute a named command, with or without parameters.

        :param command: Name of command to be executed
        :type command: str
        :param parameters: Parameters of the command
        :type parameters: str
        :return: dictionary with command result
        :rtype: dict
        """
        if self._conn is None:
            if not self.connect():
                return {
                    "status": "ERROR",
                    "info": "Not connected",
                    "command": command,
                    "retvalue": "",
                }

        path = f"http://{self._ip}:{self._port}"
        query = {"type": "command", "param": command, "value": parameters}
        res = requests.get(url=f"{path}/get/json.htm", params=query)

        if res.status_code != requests.codes.ok:
            return {
                "status": "ERROR",
                "info": "HTML status: " + str(res.raise_for_status()),
                "command": command,
                "retvalue": "",
            }
        try:
            result = res.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            result = {
                "status": "ERROR",
                "info": "HTML status: " + "timeout",
                "command": command,
                "retvalue": "",
            }
        return result

    def get_attribute(self, attribute):
        """
        Read the value associated to a named attribute.

        :param attribute: Name of attribute to be read
        :type attribute: str

        :return: result of the attribute command
        :rtype: dict
        """
        if self._conn is None:
            if not self.connect():
                return {
                    "status": "ERROR",
                    "info": "Not connected",
                    "attribute": attribute,
                    "value": None,
                }
        path = f"http://{self._ip}:{self._port}"

        query = {"type": "getattribute", "param": attribute}
        res = requests.get(url=f"{path}/get/json.htm", params=query)

        if res.status_code != requests.codes.ok:
            return {
                "status": "ERROR",
                "info": "HTML status " + str(res.raise_for_status()),
                "attribute": attribute,
                "value": None,
            }
        try:
            result = res.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            result = {
                "status": "ERROR",
                "info": "JSON Decode Error ",
                "attribute": attribute,
                "value": None,
            }
        return result

    def set_attribute(self, attribute, value):
        """
        Set the value associated to a named attribute.

        :param attribute: Name of attribute to set
        :type attribute: str
        :param value: value to set
        :type value: list or int or float

        :return: result of the attribute command
        :rtype: dict
        """
        if self._conn is None:
            if not self.connect():
                return {
                    "status": "ERROR",
                    "info": "Not connected",
                    "attribute": attribute,
                    "value": None,
                }

        path = f"http://{self._ip}:{self._port}"
        query = {"type": "set_attribute", "param": attribute, "value": value}
        res = requests.get(url=f"{path}/get/json.htm", params=query)

        if res.status_code != requests.codes.ok:
            return {
                "status": "ERROR",
                "info": "HTML status " + str(res.raise_for_status()),
                "attribute": attribute,
                "value": None,
            }
        try:
            result = res.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            result = {
                "status": "ERROR",
                "info": "JSON Decode Error ",
                "attribute": attribute,
                "value": None,
            }
        return result
