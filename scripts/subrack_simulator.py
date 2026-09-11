"""
Serve a subrack simulator over HTTP, for a client in another process to poll.

On the default port, 8081::

    PYTHONPATH=src python scripts/subrack_simulator.py

On another port, delaying every request by 400 ms::

    PYTHONPATH=src python scripts/subrack_simulator.py --port 8090 --jitter 400

The delay applies to each attribute read and to each command, so a poll sweep
of nineteen reads takes nineteen times this. Use it to hold the client's lock
long enough that a command issued during a sweep has to wait for it.

``scripts/subrack_repl.py`` is the client to point at this. Stop the server
with Ctrl-C.
"""

import argparse

import uvicorn.config

from ska_low_mccs_spshw.subrack.subrack_simulator import SubrackSimulator
from ska_low_mccs_spshw.subrack.subrack_simulator_server import run_server_forever

DEFAULT_PORT = 8081


def _quieten() -> None:
    """
    Log warnings only, rather than a line per request.

    uvicorn applies its own logging configuration when the server starts, and
    that replaces whatever the levels were set to beforehand. So the levels
    have to be changed in the configuration it is going to apply.
    """
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn.config.LOGGING_CONFIG["loggers"][name]["level"] = "WARNING"


def _parse_args() -> argparse.Namespace:
    """
    Parse the command line.

    :return: the parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"the port to serve on, or 0 for any free port (default {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--jitter",
        type=int,
        default=0,
        metavar="MS",
        help="delay every request by this many milliseconds (default 0)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="log every request, rather than warnings only",
    )
    return parser.parse_args()


def main() -> None:
    """Serve a subrack simulator until terminated."""
    args = _parse_args()

    if not args.verbose:
        _quieten()

    simulator = SubrackSimulator()
    if args.jitter:
        simulator.network_jitter_limits = (args.jitter, args.jitter + 1)
        print(f"Delaying every request by {args.jitter} ms.", flush=True)

    run_server_forever(simulator, args.port)


if __name__ == "__main__":
    main()
