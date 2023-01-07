"""This module provides an HTTP server that fronts a subrack simulator."""
import os

import fastapi
import uvicorn

from .subrack_api import SubrackProtocol, router
from .subrack_simulator import SubrackSimulator


def configure_server(
    backend: SubrackProtocol,
    host: str = "0.0.0.0",
    port: int = 8081,
) -> uvicorn.Config:
    """
    Configure a subrack simulator server.

    :param backend: the backend subrack object (hardware driver or
        simulator) to which this server will provide an interface.
    :param host: name of the interface on which to make the server
        available; defaults to "localhost".
    :param port: port number on which to run the server; defaults to
        8081

    :return: a server that is ready to be run
    """
    subrack_api = fastapi.FastAPI()
    subrack_api.state.backend = backend
    subrack_api.include_router(router)
    return uvicorn.Config(subrack_api, host=host, port=port)


def main() -> None:
    """Entry point for an HTTP server that fronts a subrack simulator."""
    subrack = SubrackSimulator()

    port = int(os.getenv("SIMULATOR_PORT", "8081"))
    server_config = configure_server(subrack, port=port)
    the_server = uvicorn.Server(config=server_config)
    the_server.run()


if __name__ == "__main__":
    main()
