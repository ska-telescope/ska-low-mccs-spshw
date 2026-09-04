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

import pytest
from ska_low_mccs_common.component import (
    HardwareClientResponseStatusCodes,
    WebHardwareClient,
)

from ska_low_mccs_spshw.prototype_subrack import Subrack, SubrackPollResponse
from ska_low_mccs_spshw.subrack.subrack_simulator import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
    SubrackServerContextManager,
)


class FakeHardwareClient:
    """
    A hardware client that returns responses given to it by a test.

    The real simulator cannot be made to report a transport level failure on
    demand, so the error branches of the client need this instead.
    """

    def __init__(self: FakeHardwareClient) -> None:
        """Initialise a new instance."""
        self.attribute_responses: dict[str, Any] = {}
        self.default_attribute_response: Any = None
        self.command_responses: dict[str, list[Any]] = {}
        self.attribute_calls: list[str] = []
        self.command_calls: list[tuple[str, str]] = []

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

    def get_attribute(self: FakeHardwareClient, attribute: str) -> Any:
        """
        Return the recorded response for an attribute read.

        :param attribute: the attribute name.

        :return: the recorded response.
        """
        self.attribute_calls.append(attribute)
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

    def execute_command(
        self: FakeHardwareClient, command: str, parameters: str = ""
    ) -> Any:
        """
        Return the recorded response for a command.

        :param command: the command name.
        :param parameters: the command arguments.

        :return: the recorded response.
        """
        self.command_calls.append((command, parameters))
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
        host,
        port,
        logger,
        poll_rate=0.1,
        command_update_rate=0.1,
        data_callback=data_callback,
        error_callback=error_callback,
        _client=WebHardwareClient(host, port),
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
        "no-such-host",
        0,
        logger,
        poll_rate=0.05,
        command_update_rate=0.05,
        data_callback=data_callback,
        error_callback=error_callback,
        _client=fake_client,  # type: ignore[arg-type]
    )
    yield subrack
    subrack.cleanup()
