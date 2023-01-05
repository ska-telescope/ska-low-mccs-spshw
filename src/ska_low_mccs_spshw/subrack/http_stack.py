"""This module provides an attribute request and response."""
from typing import Any


class HttpPollRequest:
    """
    A poll request representing payload of a request to an MCCS web server.

    Some MCCS devices monitor and control hardware by issuing HTTP GETs
    to a HTTP server running on the hardware management board. This
    object represents the payload of such a GET.

    An attribute request specifies

    * attributes whose values are to be read ("queries")
    * commands to be invoked. These commands allow for multiple
      arguments. Writing an attribute value is covered by the single-
      argument case.
    """

    def __init__(self) -> None:
        """Initialise a new instance."""
        self._getattributes: dict[str, None] = {}  # using this as a sorted set
        self._setattributes: list[tuple[str, Any]] = []
        self._commands: list[tuple[str, tuple]] = []

    def add_getattributes(self, *attributes: str) -> None:
        """
        Add attributes to be queried as part of this request.

        :param attributes: names of the attribute to be queried.
        """
        for attribute in attributes:
            self._getattributes[attribute] = None

    def add_setattribute(self, name: str, value: Any) -> None:
        """
        Add an attribute to be updated as part of this request.

        :param name: name of the command to be invoked or attribute to
            be written.
        :param value: arguments to the command. For an attribute write,
            there will only be one argument.
        """
        self._setattributes.append((name, value))

    def add_command(self, name: str, *args: Any) -> None:
        """
        Add a command to be executed as part of this request.

        :param name: name of the command to be invoked or attribute to
            be written.
        :param args: arguments to the command. For an attribute write,
            there will only be one argument.
        """
        self._commands.append((name, args))

    @property
    def getattributes(self) -> list[str]:
        """
        Return a list of getattributes queried in this request.

        :return: a list of queried attributes
        """
        return list(self._getattributes)

    @property
    def setattributes(self) -> list[tuple[str, Any]]:
        """
        Return a list of setattributes to be written in this request.

        :return: a list of name-value tuples for attributes to be
            written in this request
        """
        return list(self._setattributes)

    @property
    def commands(self) -> list[tuple[str, tuple]]:
        """
        Return the commands to be executed in this request.

        :return: a list of name-args tuples for commands to be invoked
            in this request.
        """
        return list(self._commands)


class HttpPollResponse:
    """
    Representation of an attribute response.

    An attribute response specifies values of attributes that have been
    queried in an attribute request.
    """

    def __init__(self) -> None:
        """Initialise a new instance."""
        self._query_responses: dict[str, Any] = {}
        self._command_responses: dict[str, Any] = {}

    def add_query_response(
        self,
        attribute: str,
        value: Any,
    ) -> None:
        """
        Add a response to an attribute value query.

        :param attribute: name of the queried attribute.
        :param value: value of the queried attribute.
        """
        self._query_responses[attribute] = value

    def add_command_response(
        self,
        command: str,
        value: Any,
    ) -> None:
        """
        Add a response to an command.

        :param command: name of the command.
        :param value: value returned from the command.
        """
        self._command_responses[command] = value

    @property
    def query_responses(self) -> dict[str, Any]:
        """
        Return responses to queries in an attribute request.

        :return: a dictionary of attribute values.
        """
        return dict(self._query_responses)

    @property
    def command_responses(self) -> dict[str, Any]:
        """
        Return responses to commands.

        :return: a dictionary of command return values.
        """
        return dict(self._command_responses)

    def __eq__(self, other: object) -> bool:
        """
        Check for equality with another object.

        :param other: the object against which this object is compared
            for equality.
        :return: whether the objects are equal.
        """
        if not isinstance(other, HttpPollResponse):
            return False
        if self._query_responses != other._query_responses:
            return False
        if self._command_responses != other._command_responses:
            return False
        return True
