"""
Drop into a REPL with a live subrack client.

Against the bundled simulator::

    PYTHONPATH=src python scripts/subrack_repl.py

Against a real board::

    PYTHONPATH=src python scripts/subrack_repl.py 10.0.10.80 8081

Names available afterwards are ``subrack``, ``polls``, ``errors``, ``last()``,
``show()``, ``wait()``. Exit with exit() or Ctrl-D.
"""

import code
import logging
import sys
import threading
import time

from ska_low_mccs_spshw.prototype_subrack import BoardCommandStatus, Subrack

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger("repl")

polls: list = []
errors: list = []
_arrived = threading.Event()


def _quieten() -> None:
    """
    Silence the servers that log a line per request.

    uvicorn reapplies its own logging configuration when the server starts, so
    this has to run afterwards to have any effect.
    """
    for name in ("urllib3", "uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        logger.propagate = False


def _on_data(response: object) -> None:
    polls.append(response)
    _arrived.set()


def _on_error(exception: Exception) -> None:
    errors.append(exception)
    LOGGER.error("poll failed: %r", exception)


def last() -> object:
    """
    Return the most recent poll response.

    :return: the most recent poll response, or None if there has not been one.
    """
    return polls[-1] if polls else None


def show(*keys: str) -> None:
    """
    Print values from the last poll.

    :param keys: the read keys to print. All of them if none are given.
    """
    response = last()
    if response is None:
        print("no poll yet")
        return
    wanted = keys or sorted(response.values)
    width = max(len(k) for k in wanted)
    for key in wanted:
        print(f"  {key:<{width}} {response.values.get(key)!r}"[:110])
    if response.health_status:
        print(f"  {'health_status':<{width}} <{len(response.health_status)} sections>")


def wait(timeout: float = 15.0) -> bool:
    """
    Block until the next poll arrives.

    :param timeout: how long, in seconds, to wait.

    :return: whether a poll arrived.
    """
    _arrived.clear()
    return _arrived.wait(timeout)


def commands() -> list[str]:
    """
    List the commands the board accepts.

    :return: the command names.
    """
    status, message, retvalue = subrack.run_board_command("list_commands", "")
    if status is not BoardCommandStatus.COMPLETED:
        print(f"the board would not list its commands ({message})")
        return []
    return sorted(retvalue or [])


def slow(milliseconds: int = 400) -> None:
    """
    Make the simulator delay every request.

    The delay applies to each attribute read and each command, so a poll sweep
    of nineteen reads takes nineteen times this. A command issued during a
    sweep waits for the lock, and the lock logs a warning naming its holder
    once a hold exceeds the warning threshold. Zero turns the delay off.

    Only available when running against the simulator.

    :param milliseconds: how long to delay each request.

    :raises RuntimeError: if running against a real board.
    """
    if _server is None:
        raise RuntimeError("there is no simulator, this is a real board")
    if milliseconds:
        simulator.network_jitter_limits = (milliseconds, milliseconds + 1)
    else:
        simulator.network_jitter_limits = (0, 0)
    print(f"simulator delaying every request by {milliseconds} ms")


def contend() -> None:
    """
    Run a command while a poll sweep holds the lock, and report the wait.

    Reports how long the command waited, which is the remainder of the sweep
    that was in flight.
    """
    started = time.monotonic()
    status, message, _ = subrack.run_board_command("turn_on_tpm", "2")
    waited = time.monotonic() - started
    print(f"command waited {waited:.1f}s for the lock -> {status.name} {message}")


def bye() -> None:
    """Stop the client and the simulator. Safe to call twice."""
    try:
        subrack.cleanup()
    except Exception:  # noqa: BLE001
        pass
    if _server is not None:
        _server.__exit__(None, None, None)
    LOGGER.info("stopped")


if len(sys.argv) > 1:
    HOST = sys.argv[1]
    PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8081
    _server = None
else:
    from ska_low_mccs_spshw.subrack.subrack_simulator import SubrackSimulator
    from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
        SubrackServerContextManager,
    )

    simulator = SubrackSimulator()
    _server = SubrackServerContextManager(simulator)
    HOST, PORT = _server.__enter__()
    _quieten()
    LOGGER.info("simulator on %s:%s (name: simulator)", HOST, PORT)

subrack = Subrack(
    HOST,
    PORT,
    LOGGER,
    poll_rate=2.0,
    data_callback=_on_data,
    error_callback=_on_error,
)
subrack.start_polling()
_quieten()

# Tab completion and history over the session namespace.
try:
    import readline
    import rlcompleter

    readline.set_completer(rlcompleter.Completer(globals()).complete)
    readline.parse_and_bind("tab: complete")
except ImportError:  # pragma: no cover
    pass

_BANNER = f"""\
subrack client polling {HOST}:{PORT}

  subrack    the client itself, e.g. subrack.run_board_command("turn_on_tpm", "3")
  show(*k)   print values from the last poll, all of them if given no names
  last()     the last poll response
  wait()     block until the next poll arrives
  commands() list the commands the board accepts
  slow(ms)   make the simulator delay every request
  contend()  run a command while a sweep holds the lock
  polls      every response so far
  errors     every failed poll so far
  simulator  the simulator backend, when running without an address
  bye()      stop early; exit() and Ctrl-D also shut down cleanly

Tab completes."""

# The client's polling thread is not a daemon, so it is disposed of here on
# every way out of the session, which is exit(), quit() and Ctrl-D.
try:
    code.interact(banner=_BANNER, local=globals(), exitmsg="")
finally:
    bye()
