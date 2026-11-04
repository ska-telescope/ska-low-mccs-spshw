#  -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
An SNMP simulator of the PDUs that ``MccsPdu`` drives.

The simulator is snmpsim, serving data recorded from a real PDU. The
``pdu`` variation module in ``simulator/variation`` makes a write to an
outlet's control object change that outlet's state. ``MccsPdu`` talks to the
simulator as it talks to a real PDU, with SNMP v2c and the community
``private``.

:py:func:`main` runs the simulator in the foreground, as the k8s pod does.
:py:class:`PduSimulatorContextManager` runs it in a subprocess for a test.
"""
from __future__ import annotations

import importlib.resources
import os
import socket
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from types import TracebackType
from typing import Final, Optional, TextIO

__all__ = ["PduSimulatorContextManager", "SIMULATED_MODELS", "main"]


@dataclass(frozen=True)
class SimulatedModel:
    """The data and the outlet values of one simulated PDU model."""

    data_dir: str
    """The directory under ``simulator`` that holds the recorded data."""

    on: int
    """The value ``MccsPdu`` writes to switch an outlet on."""

    off: int
    """The value ``MccsPdu`` writes to switch an outlet off."""

    state_on: int
    """The value an outlet's state object reads while the outlet is on."""

    state_off: int
    """The value an outlet's state object reads while the outlet is off."""


# The write values are the ones MccsPdu.init_device sets for each model. The
# state values are the ones the model's MIB gives.
SIMULATED_MODELS: Final[dict[str, SimulatedModel]] = {
    "ENLOGIC": SimulatedModel("enlogic", on=2, off=1, state_on=1, state_off=0),
}

DEFAULT_PORT: Final = 1610
"""The UDP port the simulator listens on, which needs no root."""

_LISTENING: Final = "Listening at UDP/IPv4 endpoint"
"""The start of the line snmpsim logs once it is ready."""


def responder_arguments(model: str, host: str, port: int, cache_dir: str) -> list[str]:
    """
    Return the snmpsim responder arguments that simulate one PDU model.

    :param model: the PDU model, a key of ``SIMULATED_MODELS``.
    :param host: the address to listen on.
    :param port: the UDP port to listen on.
    :param cache_dir: a writable directory for snmpsim's data index.

    :raises ValueError: if the model has no simulator data.

    :return: the command line arguments, without the program name.
    """
    if model not in SIMULATED_MODELS:
        raise ValueError(
            f"No simulator data for PDU model {model}. The simulated models "
            f"are {', '.join(SIMULATED_MODELS)}."
        )
    simulated = SIMULATED_MODELS[model]
    root = importlib.resources.files("ska_low_mccs_spshw.pdu.simulator")
    options = (
        f"pdu:on:{simulated.on},off:{simulated.off},"
        f"state_on:{simulated.state_on},state_off:{simulated.state_off}"
    )
    return [
        f"--data-dir={root.joinpath(simulated.data_dir)}",
        f"--variation-modules-dir={root.joinpath('variation')}",
        f"--variation-module-options={options}",
        f"--cache-dir={cache_dir}",
        f"--agent-udpv4-endpoint={host}:{port}",
        "--log-level=info",
    ]


def _discard(stream: TextIO) -> None:
    """
    Read a stream to its end and close it.

    :param stream: the stream to discard.
    """
    with stream:
        for _ in stream:
            pass


class PduSimulatorContextManager:
    """
    Run a PDU simulator in a subprocess, for a test.

    The subprocess runs snmpsim directly, so it does not import this package.
    The context waits for snmpsim to report that it is listening, and stops it
    on exit. A test can also call :py:meth:`stop` to make the PDU stop
    answering, and :py:meth:`restart` to make it answer again at the same
    address.

    snmpsim logs every request. Once it is listening, a thread keeps reading
    its log and discards it. Without that, the pipe fills, and snmpsim blocks
    on its next log write and stops answering.
    """

    def __init__(self: PduSimulatorContextManager, model: str = "ENLOGIC") -> None:
        """
        Initialise a new instance.

        :param model: the PDU model to simulate.
        """
        self._model = model
        self._address: Optional[tuple[str, int]] = None
        self._process: Optional[subprocess.Popen[str]] = None
        self._cache_dir: Optional[tempfile.TemporaryDirectory[str]] = None

    @property
    def address(self: PduSimulatorContextManager) -> tuple[str, int]:
        """
        Return where the simulator listens.

        The address stays the same after :py:meth:`stop`, so a test can show
        that nothing answers there any more.

        :raises RuntimeError: if the simulator has not been started.

        :return: the host and port.
        """
        if self._address is None:
            raise RuntimeError("The PDU simulator has not been started.")
        return self._address

    def __enter__(self: PduSimulatorContextManager) -> tuple[str, int]:
        """
        Start the simulator on a free port.

        :return: the host and port the simulator listens on.
        """
        host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind((host, 0))
            port = probe.getsockname()[1]
        return self._start(host, port)

    def restart(self: PduSimulatorContextManager) -> None:
        """
        Start the simulator again after :py:meth:`stop`, at the same address.

        The outlets start again from the recorded data.
        """
        self._start(*self.address)

    def _start(
        self: PduSimulatorContextManager, host: str, port: int
    ) -> tuple[str, int]:
        """
        Start snmpsim, and wait until it is listening.

        :param host: the address to listen on.
        :param port: the UDP port to listen on.

        :raises RuntimeError: if snmpsim stops before it is listening.

        :return: the host and port the simulator listens on.
        """
        # Both outlive this method, and stop() releases them.
        # pylint: disable=consider-using-with
        self._cache_dir = tempfile.TemporaryDirectory()
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "snmpsim.commands.responder",
                *responder_arguments(self._model, host, port, self._cache_dir.name),
            ],
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "SNMPSIM_ALLOW_ROOT": "true"},
        )
        assert self._process.stderr is not None  # for the type checker
        log = []
        for line in self._process.stderr:
            log.append(line)
            if line.lstrip().startswith(_LISTENING):
                threading.Thread(
                    target=_discard,
                    args=(self._process.stderr,),
                    name="pdu-simulator-log",
                    daemon=True,
                ).start()
                self._address = (host, port)
                return self._address
        self._process.stderr.close()
        self.stop()
        raise RuntimeError(f"The PDU simulator did not start:\n{''.join(log)}")

    def stop(self: PduSimulatorContextManager) -> None:
        """Stop the simulator, so the PDU no longer answers."""
        if self._process is not None:
            self._process.terminate()
            self._process.wait()
            self._process = None
        if self._cache_dir is not None:
            self._cache_dir.cleanup()
            self._cache_dir = None

    def __exit__(
        self: PduSimulatorContextManager,
        exc_type: Optional[type[BaseException]],
        exception: Optional[BaseException],
        trace: Optional[TracebackType],
    ) -> None:
        """
        Stop the simulator.

        :param exc_type: the type of the exception that ended the context,
            if any.
        :param exception: the exception that ended the context, if any.
        :param trace: the traceback of that exception, if any.
        """
        self.stop()


def main() -> None:
    """
    Run a PDU simulator in the foreground, as the k8s pod does.

    The model comes from ``PDU_SIMULATOR_MODEL`` (default ``ENLOGIC``), and the
    UDP port from ``PDU_SIMULATOR_PORT`` (default 1610). The simulator serves
    only test data, so it may run as root in a container.
    """
    # pylint: disable-next=import-outside-toplevel
    from snmpsim.commands import responder

    model = os.getenv("PDU_SIMULATOR_MODEL", "ENLOGIC")
    port = int(os.getenv("PDU_SIMULATOR_PORT", str(DEFAULT_PORT)))
    os.environ.setdefault("SNMPSIM_ALLOW_ROOT", "true")
    with tempfile.TemporaryDirectory() as cache_dir:
        sys.argv = [
            "pduSimulator",
            *responder_arguments(model, "0.0.0.0", port, cache_dir),
        ]
        responder.main()


if __name__ == "__main__":
    main()
