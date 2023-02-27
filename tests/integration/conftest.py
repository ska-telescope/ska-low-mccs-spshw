# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW integration tests."""
from __future__ import annotations

import functools
import socket
import threading
import time
from types import TracebackType
from typing import Any, Callable, ContextManager, Generator, Literal, Optional, Type

import pytest
import uvicorn

from ska_low_mccs_spshw.subrack import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import configure_server


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `tango_harness` fixture, causing them to be sandboxed
    in their own process.

    :param item: the collected test for which this hook is called
    """
    if "tango_harness" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


@pytest.fixture(name="subrack_simulator_factory", scope="session")
def subrack_simulator_factory_fixture(
    subrack_simulator_config: dict[str, Any],
) -> Callable[[], SubrackSimulator]:
    """
    Return a subrack simulator factory.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a subrack simulator factory.
    """
    return functools.partial(SubrackSimulator, **subrack_simulator_config)


@pytest.fixture(name="subrack_simulator")
def subrack_simulator_fixture(
    subrack_simulator_factory: Callable[[], SubrackSimulator],
) -> SubrackSimulator:
    """
    Return a subrack simulator.

    :param subrack_simulator_factory: a factory that returns a backend
        simulator to which the server will provide an interface.

    :return: a subrack simulator.
    """
    return subrack_simulator_factory()


@pytest.fixture(name="subrack_server_launcher", scope="session")
def subrack_server_launcher_fixture() -> Callable[
    [SubrackSimulator], ContextManager[tuple[str, int]]
]:
    """
    Return a subrack server launcher.

    :return: a callable that, when called, launches a subrack server for
        use in testing, yields it, and tears it down afterwards.
    """

    class _ThreadableServer(uvicorn.Server):
        def install_signal_handlers(self: _ThreadableServer) -> None:
            pass

    class _SubrackServerContextManager:
        def __init__(
            self: _SubrackServerContextManager,
            subrack_simulator: SubrackSimulator,
        ) -> None:
            self._socket = socket.socket()
            server_config = configure_server(
                subrack_simulator, host="127.0.0.1", port=0
            )
            self._server = _ThreadableServer(config=server_config)
            self._thread = threading.Thread(
                target=self._server.run, args=([self._socket],), daemon=True
            )

        def __enter__(self: _SubrackServerContextManager) -> tuple[str, int]:
            self._thread.start()

            while not self._server.started:
                time.sleep(1e-3)
            _, port = self._socket.getsockname()
            return "127.0.0.1", port

        def __exit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exception: Optional[BaseException],
            trace: Optional[TracebackType],
        ) -> Literal[False]:
            """
            Exit the context.

            :param exc_type: the type of exception thrown in the with block
            :param exception: the exception thrown in the with block
            :param trace: a traceback

            :returns: whether the exception (if any) has been fully handled
                by this method and should be swallowed i.e. not re-raised
            """
            self._server.should_exit = True
            self._thread.join()
            return False

    return _SubrackServerContextManager


@pytest.fixture(name="subrack_address")
def subrack_address_fixture(
    subrack_server_launcher: Callable[
        [SubrackSimulator], ContextManager[tuple[str, int]]
    ],
    subrack_simulator: SubrackSimulator,
) -> Generator[tuple[str, int], None, None]:
    """
    Yield the host and port of a running subrack server.

    :param subrack_server_launcher: a callable that, when called,
        returns a context manager that spins up a subrack server, yields
        it for use in testing, and then shuts its down afterwards.
    :param subrack_simulator: the actual backend simulator to which this
        server provides an interface.

    :yields: the host and port of a running subrack server.
    """
    with subrack_server_launcher(subrack_simulator) as (host, port):
        yield host, port
