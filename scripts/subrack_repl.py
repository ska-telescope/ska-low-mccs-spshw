"""
Drop into a REPL with a live subrack client. Holds no board of its own.

Start a simulator in another terminal first::

    PYTHONPATH=src python scripts/subrack_simulator.py

Then, against that simulator on 127.0.0.1:8081::

    PYTHONPATH=src python scripts/subrack_repl.py

Against a real board, or a simulator elsewhere::

    PYTHONPATH=src python scripts/subrack_repl.py 10.0.10.80 8081

Names available afterwards are ``subrack``, ``polls``, ``errors``, ``last()``,
``show()``, ``wait()``. Exit with exit() or Ctrl-D.
"""

import code
import logging
import sys
import threading
import time

from ska_low_mccs_common.component import WebHardwareClient

from ska_low_mccs_spshw.prototype_subrack import (
    BoardCommandStatus,
    Subrack,
    SubrackPoller,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8081
POLL_RATE = 2.0

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger("repl")

polls: list = []
errors: list = []
_arrived = threading.Event()


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


def contend() -> None:
    """
    Run a command while a poll sweep holds the lock, and report the wait.

    Reports how long the command waited, which is the remainder of the sweep
    that was in flight. Start the simulator with ``--jitter 400`` to make each
    sweep slow enough for the wait to be worth measuring.
    """
    started = time.monotonic()
    status, message, _ = subrack.run_board_command("turn_on_tpm", "2")
    waited = time.monotonic() - started
    print(f"command waited {waited:.1f}s for the lock -> {status.name} {message}")


def bye() -> None:
    """Stop polling. Safe to call twice."""
    try:
        poller.kill_polling_thread()
    except Exception:  # noqa: BLE001
        pass
    LOGGER.info("stopped")


HOST = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

# The client logs a line per request, which a poll sweep makes nineteen of.
logging.getLogger("urllib3").setLevel(logging.WARNING)

client = WebHardwareClient(HOST, PORT)
if client.get_attribute("board_current")["status"] not in ("OK", "ERROR"):
    LOGGER.warning(
        "Nothing is answering on %s:%s. If you meant the simulator, start it "
        "with: PYTHONPATH=src python scripts/subrack_simulator.py",
        HOST,
        PORT,
    )

subrack = Subrack(
    client,
    HOST,
    LOGGER,
    data_callback=_on_data,
    error_callback=_on_error,
)
# The subrack answers polls but does not run them. This owns the thread.
poller = SubrackPoller(subrack, POLL_RATE, LOGGER)
poller.start_polling()

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
  poller     the poll loop driving it, e.g. poller.stop_polling()
  show(*k)   print values from the last poll, all of them if given no names
  last()     the last poll response
  wait()     block until the next poll arrives
  commands() list the commands the board accepts
  contend()  run a command while a sweep holds the lock
  polls      every response so far
  errors     every failed poll so far
  bye()      stop early; exit() and Ctrl-D also shut down cleanly

The board runs in its own process. To delay its every request, restart it with
scripts/subrack_simulator.py --jitter 400

Tab completes."""

# The poller's thread is not a daemon, so it is disposed of here on every way
# out of the session, which is exit(), quit() and Ctrl-D.
try:
    code.interact(banner=_BANNER, local=globals(), exitmsg="")
finally:
    bye()
