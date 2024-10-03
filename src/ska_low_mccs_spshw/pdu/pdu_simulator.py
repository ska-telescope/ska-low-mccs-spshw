# -*- coding: utf-8 -*-
#
# This file is part of the SKA MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""This module implements a standlone PDU simulator."""

from __future__ import annotations  # allow forward references in type hints

import logging
import signal
import subprocess
import threading
import time
from typing import Any

from tango import DevState
from tango.server import Device, attribute, device_property

__all__ = ["PduSimulator"]


# pylint: disable=too-many-instance-attributes
class PduSimulatorServer:
    """Simulator server."""

    def __init__(self: PduSimulatorServer, *args: Any, **kwargs: Any) -> None:
        """
        Initialise the server.

        :param args: positional arguments
        :param kwargs: named arguments
        """
        self._host = args[0]
        self._port = int(args[1])
        self._logger = args[2]
        self._user_args = []
        if "sim_user" in kwargs:
            sim_user = kwargs.pop("sim_user")
            if sim_user and ":" in sim_user:
                user, group = sim_user.split(":")
                self._user_args = [f"--process-user={user}", f"--process-group={group}"]

        if "data_dir" in kwargs:
            self._data_dir = kwargs.pop("data_dir")
        else:
            self._data_dir = "tests/unit/whiterabbit/snmpsim_data/switch"

        self._lock = threading.RLock()
        self._server_ready = False
        self._thread = threading.Thread(target=self.monitor, daemon=False)
        self._logger.info("Thread task starting now")
        self._thread.start()

    def is_server_ready(self: PduSimulatorServer) -> bool:
        """
        Check if the simulator server is up and listening.

        :return: True if server is ready else False
        """
        return self._server_ready

    def monitor(self: PduSimulatorServer) -> None:
        """Create a runnable thread function for the server."""
        # pylint: disable=consider-using-with
        sim_process: Any = subprocess.Popen(  # type Any for mypy
            [
                "snmpsim-command-responder",
                *self._user_args,
                f"--data-dir={self._data_dir}",
                f"--agent-udpv4-endpoint={self._host}:{self._port}",
            ],
            encoding="utf-8",
            stderr=subprocess.PIPE,
        )
        try:
            while sim_process.poll() is None:
                line = sim_process.stderr.readline()
                if line.startswith("  Listening"):
                    with self._lock:
                        self._server_ready = True
                    break
        finally:
            try:
                sim_process.wait()
            # pylint: disable=broad-exception-caught
            except Exception:
                sim_process.send_signal(signal.SIGTERM)
                self._logger.info("finally")


class PduSimulator(Device):
    """Pdu device simulator for SAT.LMC."""

    # -----------------
    # Device Properties
    # -----------------
    Host = device_property(dtype=str, default_value="127.0.0.1")
    Port = device_property(dtype=int, default_value=1610)
    DataDir = device_property(dtype=str, default_value="")
    SimUser = device_property(dtype=str, default_value="")

    # ---------------
    # General methods
    # ---------------
    def __init__(self: PduSimulator, *args: Any, **kwargs: Any) -> None:
        """
        Initialise this device object.

        :param args: positional args to the init
        :param kwargs: keyword args to the init
        """
        super().__init__(*args, **kwargs)
        self._simserver: PduSimulatorServer | None

    def init_device(self: PduSimulator) -> None:
        """Initialise the device."""
        super().init_device()
        self.set_state(DevState.INIT)
        logging.basicConfig(level=logging.INFO)
        self._logger = logging.getLogger(self.__class__.__name__)
        try:
            self._simserver = PduSimulatorServer(
                self.Host,
                self.Port,
                self._logger,
                data_dir=self.DataDir,
                sim_user=self.SimUser,
            )
            assert self._simserver
            while not self._simserver.is_server_ready():
                time.sleep(0.1)
            time.sleep(0.5)

        # pylint: disable=broad-exception-caught
        except Exception as ex:
            self._logger.error(
                "Catch already bound exceptions when trying use the init command"
            )
            self._logger.error(repr(ex))

        self.set_state(DevState.ON)

    def delete_device(self: PduSimulator) -> None:
        """Delete resources allocated in init_device."""
        self._simserver = None

    @attribute(
        dtype="boolean",
    )
    def is_server_ready(self: PduSimulator) -> bool:
        """
        Report the locsimulator server status.

        :return: the server status
        """
        assert self._simserver
        return self._simserver.is_server_ready()


# ----------
# Run server
# ----------
def main(*args: str, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments
    :return: exit code
    """
    return PduSimulator.run_server(args=args or None, **kwargs)


if __name__ == "__main__":
    main()
