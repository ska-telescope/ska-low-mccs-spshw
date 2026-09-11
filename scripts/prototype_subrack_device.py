"""
Run an MccsPrototypeSubrack Tango device server.

The device is served through the same entry point a deployment uses, with its
properties supplied by a Tango file database that this script writes and then
removes.

Start a subrack simulator in another terminal first::

    PYTHONPATH=src python scripts/prototype_subrack_device.py

Against a real board, or a simulator elsewhere::

    PYTHONPATH=src python scripts/prototype_subrack_device.py 10.0.10.80 8081

The script prints the TRL to connect with. From another process, with the
device online by default::

    import tango
    device = tango.DeviceProxy("<the TRL it printed>")
    print(device.state(), device.healthState)
    print(device.boardTemperatures, device.subrackFanSpeeds)

Pass ``--offline`` to start in adminMode OFFLINE instead, so that the move into
monitoring can be driven manually. Stop the server with Ctrl-C.
"""

import argparse
import os
import socket
import sys
import tempfile

import tango
from ska_control_model import AdminMode

from ska_low_mccs_spshw.prototype_subrack.prototype_subrack_device import (
    subrack_factory,
)

DEFAULT_SUBRACK_HOST = "127.0.0.1"
DEFAULT_SUBRACK_PORT = 8081
DEFAULT_DEVICE_PORT = 45678
DEFAULT_TRL = "low-mccs/prototypesubrack/1"
DEFAULT_UPDATE_RATE = 2.0
DEVICE_CLASS = "MccsPrototypeSubrack"
INSTANCE = "prototype"


def _parse_args() -> argparse.Namespace:
    """
    Parse the command line.

    :return: the parsed arguments.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "subrack_host",
        nargs="?",
        default=DEFAULT_SUBRACK_HOST,
        help=f"host of the subrack to poll (default {DEFAULT_SUBRACK_HOST})",
    )
    parser.add_argument(
        "subrack_port",
        nargs="?",
        type=int,
        default=DEFAULT_SUBRACK_PORT,
        help=f"port of the subrack to poll (default {DEFAULT_SUBRACK_PORT})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DEVICE_PORT,
        help=f"the port to serve the device on (default {DEFAULT_DEVICE_PORT})",
    )
    parser.add_argument(
        "--host",
        default=socket.gethostname(),
        help="the host to bind to and advertise (default this machine's name)",
    )
    parser.add_argument(
        "--trl",
        default=DEFAULT_TRL,
        help=f"the Tango device name to serve (default {DEFAULT_TRL})",
    )
    parser.add_argument(
        "--update-rate",
        type=float,
        default=DEFAULT_UPDATE_RATE,
        metavar="SECONDS",
        help=f"how often to poll the subrack (default {DEFAULT_UPDATE_RATE})",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="start in adminMode OFFLINE, rather than ONLINE and polling",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="ask Tango for verbose server logging",
    )
    return parser.parse_args()


def _write_file_database(path: str, args: argparse.Namespace) -> None:
    """
    Write the Tango file database the server reads its properties from.

    The first line registers the device against the server instance. The
    properties and the memorized ``adminMode`` are then written through the
    Tango database API, so the file is in whatever format this Tango expects.

    :param path: where to write the file database.
    :param args: the parsed command line.
    """
    with open(path, "w", encoding="utf-8") as database_file:
        database_file.write(
            f"{DEVICE_CLASS}/{INSTANCE}/DEVICE/{DEVICE_CLASS}: {args.trl}\n"
        )

    database = tango.Database(path)
    database.put_device_property(
        args.trl,
        {
            "SubrackIp": [args.subrack_host],
            "SubrackPort": [str(args.subrack_port)],
            "UpdateRate": [str(args.update_rate)],
        },
    )
    admin_mode = AdminMode.OFFLINE if args.offline else AdminMode.ONLINE
    # adminMode is memorized, so this is how the device is told to start
    # monitoring without a client having to write it.
    database.put_device_attribute_property(
        args.trl, {"adminMode": {"__value": [str(int(admin_mode))]}}
    )


def _announce(args: argparse.Namespace) -> None:
    """
    Say what is being served, and how to reach it.

    :param args: the parsed command line.
    """
    admin_mode = AdminMode.OFFLINE if args.offline else AdminMode.ONLINE
    trl = f"tango://{args.host}:{args.port}/{args.trl}#dbase=no"
    print(f"\nServing {args.trl}", flush=True)
    print(
        f"Polling {args.subrack_host}:{args.subrack_port} "
        f"every {args.update_rate}s",
        flush=True,
    )
    print(f"adminMode {admin_mode.name}", flush=True)
    print(f"\nConnect with:\n\n    {trl}\n", flush=True)
    print("Stop with Ctrl-C.\n", flush=True)


def main() -> int:
    """
    Serve one prototype subrack device until terminated.

    :return: the exit code.
    """
    args = _parse_args()

    handle, database_path = tempfile.mkstemp(prefix="prototype-subrack-", suffix=".db")
    os.close(handle)
    try:
        _write_file_database(database_path, args)
        _announce(args)

        server_args = [
            INSTANCE,
            "-ORBendPoint",
            f"giop:tcp:{args.host}:{args.port}",
            f"-file={database_path}",
        ]
        if args.verbose:
            server_args.append("-v4")

        subrack_factory().run_server(args=server_args)
    except KeyboardInterrupt:
        print("\nStopping.", flush=True)
    finally:
        os.unlink(database_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
