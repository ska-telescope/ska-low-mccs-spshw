#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module provides an HTTP server that fronts a subrack simulator."""
from __future__ import annotations

import os
import socket
import threading
import time
from types import TracebackType
from typing import Literal, Optional, Type

import fastapi
import uvicorn

from .subrack_api import SubrackProtocol, router
from .subrack_simulator import SubrackSimulator


def _configure_server(
    backend: SubrackProtocol,
    host: str = "0.0.0.0",
    port: int = 8081,
) -> uvicorn.Config:
    """
    Configure a subrack simulator server.

    :param backend: the backend subrack object (hardware driver or
        simulator) to which this server will provide an interface.
    :param host: name of the interface on which to make the server
        available; defaults to "0.0.0.0" (all interfaces).
    :param port: port number on which to run the server; defaults to
        8081

    :return: a server that is ready to be run
    """
    subrack_api = fastapi.FastAPI()
    subrack_api.state.backend = backend
    subrack_api.include_router(router)
    return uvicorn.Config(subrack_api, host=host, port=port)


class _ThreadableServer(uvicorn.Server):
    def install_signal_handlers(self: _ThreadableServer) -> None:
        pass


class SubrackServerContextManager:
    """A context manager for a subrack server."""

    def __init__(
        self: SubrackServerContextManager,
        backend: SubrackProtocol | None = None,
    ) -> None:
        """
        Initialise a new instance.

        :param backend: the backend for which that this subrack server
            provides web access.
        """
        self._socket = socket.socket()
        server_config = _configure_server(
            backend or SubrackSimulator(), host="127.0.0.1", port=0
        )
        self._server = _ThreadableServer(config=server_config)
        self._thread = threading.Thread(
            target=self._server.run, args=([self._socket],), daemon=True
        )

    def __enter__(self: SubrackServerContextManager) -> tuple[str, int]:
        """
        Enter the context in which the subrack server is running.

        That is, start up the subrack server.

        :return: the host and port of the running subrack server.
        """
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
        Exit the context in which the subrack server is running.

        That is, shut down the server.

        :param exc_type: the type of exception thrown in the with block
        :param exception: the exception thrown in the with block
        :param trace: a traceback

        :returns: whether the exception (if any) has been fully handled
            by this method and should be swallowed i.e. not re-raised
        """
        self._server.should_exit = True
        self._thread.join()
        return False


def run_server_forever(backend: SubrackProtocol, port: int) -> None:
    """
    Run the subrack server until terminated.

    :param backend: the backend for which this server provides an interface.
    :param port: the port on which to run the server.
        If set to 0, the server will be run on any available port.
        The actual port on which the server is running
        will be printed to stdout.
    """
    print("Starting daq server...", flush=True)
    server_config = _configure_server(backend, port=port)
    the_server = uvicorn.Server(config=server_config)
    the_server.run()
    print("Stopping daq server.")


def main() -> None:
    """Entry point for an HTTP server that fronts a subrack simulator."""
    subrack = SubrackSimulator()

    port = int(os.getenv("SUBRACK_SIMULATOR_PORT", "8081"))
    run_server_forever(subrack, port)


if __name__ == "__main__":
    main()
