# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module defined a pytest harness for testing the MCCS subrack module."""
from __future__ import annotations

import functools
import logging
import socket
import threading
import time
from types import TracebackType
from typing import (
    Any,
    Callable,
    ContextManager,
    Generator,
    Literal,
    Optional,
    Type,
    TypedDict,
)

import pytest
import uvicorn
from ska_control_model import PowerState
from ska_low_mccs_common.testing.mock import MockCallable

from ska_low_mccs_spshw.subrack import (
    SubrackComponentManager,
    SubrackDriver,
    SubrackSimulator,
)
from ska_low_mccs_spshw.subrack.subrack_simulator_server import configure_server

SubrackInfoType = TypedDict(
    "SubrackInfoType", {"host": str, "port": int, "simulator": bool}
)


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


@pytest.fixture(name="subrack_driver")
def subrack_driver_fixture(
    subrack_address: tuple[str, int],
    logger: logging.Logger,
    callbacks: dict[str, MockCallable],
) -> SubrackDriver:
    """
    Return a subrack driver, configured to talk to a running subrack server.

    (This is a pytest fixture.)

    :param subrack_address: the host and port of the subrack
    :param logger: the logger to be used by this object.
    :param callbacks: dictionary of driver callbacks

    :return: a subrack driver.
    """
    subrack_ip, subrack_port = subrack_address
    return SubrackDriver(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        update_rate=1.0,
    )


@pytest.fixture(name="subrack_component_manager")
def subrack_component_manager_fixture(
    logger: logging.Logger,
    subrack_address: tuple[str, int],
    subrack_driver: SubrackDriver,
    initial_power_state: PowerState,
    callbacks: dict[str, MockCallable],
) -> SubrackComponentManager:
    """
    Return an subrack component manager (in simulation mode as specified).

    (This is a pytest fixture.)

    :param logger: the logger to be used by this object.
    :param subrack_address: the host and port of the subrack
    :param subrack_driver: the subrack driver to use. Normally the
        subrack component manager creates its own driver; here we inject
        this driver instead.
    :param initial_power_state: the initial power state of the upstream
        power supply
    :param callbacks: dictionary of driver callbacks

    :return: an subrack component manager in the specified simulation mode.
    """
    subrack_ip, subrack_port = subrack_address
    return SubrackComponentManager(
        subrack_ip,
        subrack_port,
        logger,
        callbacks["communication_status"],
        callbacks["component_state"],
        _driver=subrack_driver,
        _initial_power_state=initial_power_state,
    )


@pytest.fixture(name="callbacks")
def callbacks_fixture() -> dict[str, MockCallable]:
    """
    Return a dictionary of callables to be used as callbacks.

    :return: a dictionary of callables to be used as callbacks.
    """
    return {
        "communication_status": MockCallable(),
        "component_state": MockCallable(),
        "task": MockCallable(),
    }
