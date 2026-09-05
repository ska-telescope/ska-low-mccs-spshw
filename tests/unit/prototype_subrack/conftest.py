#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Fixtures for the prototype subrack tests."""

from __future__ import annotations

import logging
import queue
from typing import Any, Iterator
from unittest import mock

import pytest
from ska_low_mccs_common.component import (
    HardwareClientResponseStatusCodes,
    WebHardwareClient,
)

from ska_low_mccs_spshw.prototype_subrack import (
    Subrack,
    SubrackPoller,
    SubrackPollResponse,
)
from ska_low_mccs_spshw.subrack.subrack_simulator import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
    SubrackServerContextManager,
)


class FakeHardwareClient:
    """
    A hardware client that returns the responses a test gives it.

    A response can be set per attribute name, or as a default for every
    attribute. Command responses are set per command name, as a sequence that
    is returned in order, with the last one repeating.
    """

    def __init__(self: FakeHardwareClient) -> None:
        """
        Initialise a new instance.

        ``get_attribute`` and ``execute_command`` are mocks whose side effect
        is the dispatch below, so both the calls and the responses are
        available.
        """
        self.attribute_responses: dict[str, Any] = {}
        self.default_attribute_response: Any = None
        self.command_responses: dict[str, list[Any]] = {}
        self.get_attribute = mock.Mock(
            name="get_attribute", side_effect=self._get_attribute
        )
        self.execute_command = mock.Mock(
            name="execute_command", side_effect=self._execute_command
        )

    @property
    def attribute_calls(self: FakeHardwareClient) -> list[str]:
        """
        Return the attribute names read, in order.

        :return: the attribute names read.
        """
        return [call.args[0] for call in self.get_attribute.call_args_list]

    @property
    def command_calls(self: FakeHardwareClient) -> list[tuple[str, str]]:
        """
        Return the commands run, in order, as name and argument pairs.

        :return: the commands run.
        """
        return [
            (call.args[0], call.args[1] if len(call.args) > 1 else "")
            for call in self.execute_command.call_args_list
        ]

    def set_attribute_response(self: FakeHardwareClient, **kwargs: Any) -> Any:
        """
        Build and record a response for every attribute read.

        :param kwargs: fields to override on the response.

        :return: the response that was recorded.
        """
        response = {
            "status": HardwareClientResponseStatusCodes.OK.name,
            "info": "",
            "attribute": "",
            "value": None,
        }
        response.update(kwargs)
        self.default_attribute_response = response
        return response

    def set_command_responses(
        self: FakeHardwareClient, command: str, *responses: Any
    ) -> None:
        """
        Record the responses to return for a command, in order.

        The last response is repeated once the list runs out.

        :param command: the command name.
        :param responses: the responses to return, in order.
        """
        self.command_responses[command] = list(responses)

    def _get_attribute(self: FakeHardwareClient, attribute: str) -> Any:
        """
        Return the recorded response for an attribute read.

        :param attribute: the attribute name.

        :return: the recorded response.
        """
        if attribute in self.attribute_responses:
            return self.attribute_responses[attribute]
        if self.default_attribute_response is not None:
            return dict(self.default_attribute_response, attribute=attribute)
        return {
            "status": HardwareClientResponseStatusCodes.OK.name,
            "info": "",
            "attribute": attribute,
            "value": None,
        }

    def _execute_command(
        self: FakeHardwareClient, command: str, parameters: str = ""
    ) -> Any:
        """
        Return the recorded response for a command.

        :param command: the command name.
        :param parameters: the command arguments.

        :return: the recorded response.
        """
        responses = self.command_responses.get(command)
        if not responses:
            return {
                "status": HardwareClientResponseStatusCodes.OK.name,
                "info": "",
                "command": command,
                "retvalue": "",
            }
        if len(responses) > 1:
            return responses.pop(0)
        return responses[0]


@pytest.fixture(name="logger")
def logger_fixture() -> logging.Logger:
    """
    Return a logger for the tests to use.

    :return: a logger.
    """
    return logging.getLogger("test-prototype-subrack")


@pytest.fixture(name="fake_client")
def fake_client_fixture() -> FakeHardwareClient:
    """
    Return a hardware client that a test drives directly.

    :return: a fake hardware client.
    """
    return FakeHardwareClient()


@pytest.fixture(name="subrack_simulator")
def subrack_simulator_fixture(
    subrack_simulator_config: dict[str, Any],
) -> SubrackSimulator:
    """
    Return a subrack simulator.

    :param subrack_simulator_config: the values with which to configure it.

    :return: a subrack simulator.
    """
    return SubrackSimulator(**subrack_simulator_config)


@pytest.fixture(name="simulator_address")
def simulator_address_fixture(
    subrack_simulator: SubrackSimulator,
) -> Iterator[tuple[str, int]]:
    """
    Run a subrack simulator server, and return its address.

    :param subrack_simulator: the simulator to serve.

    :yields: the host and port of the running simulator server.
    """
    with SubrackServerContextManager(subrack_simulator) as (host, port):
        yield (host, port)


@pytest.fixture(name="responses")
def responses_fixture() -> queue.SimpleQueue:
    """
    Return a queue into which the client pushes its callback arguments.

    :return: a queue of poll responses and exceptions.
    """
    return queue.SimpleQueue()


@pytest.fixture(name="callbacks")
def callbacks_fixture(
    responses: queue.SimpleQueue,
) -> tuple[Any, Any]:
    """
    Return a data callback and an error callback that both feed the queue.

    :param responses: the queue to feed.

    :return: the data callback and the error callback.
    """

    def data_callback(response: SubrackPollResponse) -> None:
        responses.put(response)

    def error_callback(exception: Exception) -> None:
        responses.put(exception)

    return (data_callback, error_callback)


@pytest.fixture(name="simulated_subrack")
def simulated_subrack_fixture(
    simulator_address: tuple[str, int],
    logger: logging.Logger,
    callbacks: tuple[Any, Any],
) -> Iterator[Subrack]:
    """
    Return a client that talks to a real simulator server over HTTP.

    :param simulator_address: the host and port of the simulator server.
    :param logger: a logger.
    :param callbacks: the data callback and the error callback.

    :yields: a subrack client.
    """
    (host, port) = simulator_address
    (data_callback, error_callback) = callbacks
    subrack = Subrack(
        WebHardwareClient(host, port),
        host,
        logger,
        poller_factory=lambda model: SubrackPoller(model, 0.1, logger),
        data_callback=data_callback,
        error_callback=error_callback,
    )
    yield subrack
    subrack.cleanup()


@pytest.fixture(name="faked_subrack")
def faked_subrack_fixture(
    fake_client: FakeHardwareClient,
    logger: logging.Logger,
    callbacks: tuple[Any, Any],
) -> Iterator[Subrack]:
    """
    Return a client whose hardware client is a test controlled fake.

    :param fake_client: the fake hardware client.
    :param logger: a logger.
    :param callbacks: the data callback and the error callback.

    :yields: a subrack client.
    """
    (data_callback, error_callback) = callbacks
    subrack = Subrack(
        fake_client,  # type: ignore[arg-type]
        "no-such-host",
        logger,
        poller_factory=lambda model: SubrackPoller(model, 0.05, logger),
        data_callback=data_callback,
        error_callback=error_callback,
    )
    yield subrack
    subrack.cleanup()
