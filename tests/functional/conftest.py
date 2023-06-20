# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for SPSHW functional tests."""
from __future__ import annotations

import os
import socket
import threading
import time
import queue
from contextlib import contextmanager
from types import TracebackType
from functools import lru_cache
from typing import (
    Any,
    Callable,
    ContextManager,
    Generator,
    Literal,
    Optional,
    Type,
    Union,
    cast,
    TypedDict,
)

import _pytest
import pytest
import tango
from pytest_bdd import given, parsers, then, when
from ska_control_model import LoggingLevel, AdminMode, ResultCode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
    TrueTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from ska_tango_testing.mock.placeholders import OneOf

DeviceMapping = TypedDict("DeviceMapping", {"name": str, "subscriptions": list[str]})

# TODO: https://github.com/pytest-dev/pytest-forked/issues/67
# We're stuck on pytest 6.2 until this gets fixed, and this version of
# pytest is not fully typehinted
def pytest_addoption(
    parser: _pytest.config.argparsing.Parser,  # type: ignore[name-defined]
) -> None:
    """
    Add a command line option to pytest.

    This is a pytest hook, here implemented to add the `--true-context`
    option, used to indicate that a true Tango subsystem is available,
    so there is no need for the test harness to spin up a Tango test
    context.

    :param parser: the command line options parser
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        default=False,
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )

@pytest.fixture(name="tango_context", scope="session")
def tango_context_fixture() -> Generator[TangoContextProtocol, None, None]:
    """
    Yield a Tango context containing the device/s under test.

    :yields: a Tango context containing the devices under test
    """
    with TrueTangoContextManager() as context:
        yield context

@pytest.fixture(name="tpm_1_number", scope="session")
def tpm_number_1_fixture() -> int:
    """
    Return the number of the TPM under test in the subrack under test.

    :returns: the number of the TPM
    """
    return 2

@pytest.fixture(name="tpm_2_number", scope="session")
def tpm_number_2_fixture() -> int:
    """
    Return the number of the TPM under test in the subrack under test.

    :returns: the number of the TPM
    """
    return 5


@pytest.fixture(name="true_context", scope="session")
def true_context_fixture(request: pytest.FixtureRequest) -> bool:
    """
    Return whether to test against an existing Tango deployment.

    If True, then Tango is already deployed, and the tests will be run
    against that deployment.

    If False, then Tango is not deployed, so the test harness will stand
    up a test context and run the tests against that.

    :param request: A pytest object giving access to the requesting test
        context.

    :return: whether to test against an existing Tango deployment
    """
    if request.config.getoption("--true-context"):
        return True
    if os.getenv("TRUE_TANGO_CONTEXT", None):
        return True
    return False


@pytest.fixture(name="subrack_address_context_manager_factory", scope="module")
def subrack_address_context_manager_factory_fixture(
    subrack_simulator_config: dict[str, Any],
) -> Callable[[], ContextManager[tuple[str, int]]]:
    """
    Return the subrack address context manager factory.

    That is, return a callable that, when called, provides a context
    manager that, when entered, returns a subrack host and port, while
    at the same time ensuring the validity of that host and port.

    This fixture obtains the subrack address in one of two ways:

    Firstly it checks for a `SUBRACK_ADDRESS` environment variable, of
    the form "localhost:8081". If found, it is expected that a subrack
    is already available at this host and port, so there is nothing more
    for this fixture to do. The callable that it returns, will itself
    return an empty context manager that, when entered, simply yields
    the specified host and port.

    Otherwise, the callable that this factory returns will be a context
    manager for a subrack simulator server instance. When entered, that
    context manager will launch the subrack simulator server, and then
    yield the host and port on which it is running.

    :param subrack_simulator_config: a keyword dictionary that specifies
        the desired configuration of the simulator backend.

    :return: a callable that returns a context manager that, when
        entered, yields the host and port of a subrack server.
    """
    address_var = "SUBRACK_ADDRESS"
    if address_var in os.environ:
        [host, port_str] = os.environ[address_var].split(":")

        @contextmanager
        def _yield_address() -> Generator[tuple[str, int], None, None]:
            yield host, int(port_str)

        return _yield_address
    else:

        class _SubrackServerContextManager:
            def __init__(self: _SubrackServerContextManager) -> None:
                # Imports are deferred until now,
                # so that we do not try to import from ska_low_mccs_spshw
                # until we know that we need to.
                # This allows us to runour functional tests
                # against a real cluster
                # from within a test runner pod
                # that does not have ska_low_mccs_spshw installed.
                import uvicorn

                from ska_low_mccs_spshw.subrack import SubrackSimulator
                from ska_low_mccs_spshw.subrack.subrack_simulator_server import (
                    configure_server,
                )

                class _ThreadableServer(uvicorn.Server):
                    def install_signal_handlers(self: _ThreadableServer) -> None:
                        pass

                server_config = configure_server(
                    SubrackSimulator(**subrack_simulator_config),
                    host="127.0.0.1",
                    port=0,
                )
                self._server = _ThreadableServer(config=server_config)
                self._socket = socket.socket()
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
                self: _SubrackServerContextManager,
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

                :raises ImportError: if this context manager is running in an
                    environment that does not have ska_low_mccs_spshw installed.
                """
                if exc_type is ImportError:
                    raise ImportError(
                        """Error: you must do one of the following:
                        * use "--true-context" flag or TRUE_TANGO_CONTEXT environment
                          variable to run these tests against a pre-deployed cluster in
                          which the Tango device under test is already running.
                        * use SUBRACK_ADDRESS environment variable to specify the host
                          and port of a subrack server. The test harness will stand up
                          the Tango device under test to monitor and control the subrack
                          at that server address.
                        * run these tests in an environment in which ska_low_mccs_spshw
                          and its dependencies are installed. The test harness will
                          stand up its own subrack simulator server, and then stand up
                          the Tango device under test to monitor and control that
                          subrack simulator server."""
                    ) from exception

                self._server.should_exit = True
                self._thread.join()

                return False

        return _SubrackServerContextManager


@pytest.fixture(name="tango_harness", scope="module")
def tango_harness_fixture(
    subrack_name: str,
    subrack_address_context_manager_factory: Callable[
        [], ContextManager[tuple[str, int]]
    ],
    true_context: bool,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Yield a Tango context containing the device/s under test.

    :param subrack_name: name of the subrack Tango device.
    :param subrack_address_context_manager_factory: a callable that
         returns a context manager that, when entered, yields the host
         and port of a subrack.
    :param true_context: whether to test against an existing Tango
        deployment

    :yields: a Tango context containing the devices under test
    """
    tango_context_manager: Union[
        TrueTangoContextManager, ThreadedTestTangoContextManager
    ]  # for the type checker
    if true_context:
        tango_context_manager = TrueTangoContextManager()
        with tango_context_manager as context:
            yield context
    else:
        with subrack_address_context_manager_factory() as (host, port):
            tango_context_manager = ThreadedTestTangoContextManager()
            cast(ThreadedTestTangoContextManager, tango_context_manager).add_device(
                subrack_name,
                "ska_low_mccs_spshw.MccsSubrack",
                SubrackIp=host,
                SubrackPort=port,
                UpdateRate=1.0,
                LoggingLevelDefault=int(LoggingLevel.DEBUG),
            )
            with tango_context_manager as context:
                yield context


@pytest.fixture(name="change_event_callbacks", scope="session")
def change_event_callbacks_fixture(
    device_mapping: dict[str, DeviceMapping],
) -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of change event callbacks with asynchrony support.

    :param device_mapping: a map from short to canonical device names

    :returns: a callback group.
    """
    keys = [
        f"{info['name']}/{attr}"
        for info in device_mapping.values()
        for attr in info["subscriptions"]
    ]

    return MockTangoEventCallbackGroup(
        *keys,
        timeout=60.0,  # TPM takes a long time to initialise
    )


@pytest.fixture(name="device_mapping", scope="session")
def device_mapping_fixture(tpm_1_number: int, tpm_2_number) -> dict[str, DeviceMapping]:
    """
    Return a mapping from short to canonical Tango device names.

    :param tpm_number: the sequence number of the TPM in use

    :return: a map of short names to full Tango device names of the form
        "<domain>/<class>/<instance>"
    """
    return {
        "station": {
            "name" : "low-mccs/station/001",
            "subscriptions" : [
                "adminMode",
                "state",
                #"tileprogrammingstate"
            ]
        },
        "subrack": {
            "name": "low-mccs/subrack/0001",
            "subscriptions": [
                "adminMode",
                "state",
                f"tpm{tpm_1_number}PowerState",
                f"tpm{tpm_2_number}PowerState",
                "subrackFanModes",
                "subrackFanSpeeds",
                #"subrackFanPercent",
                "subrackFanSpeedsPercent",
                "tpmPresent",
            ],
        },
        "tile_1": {
            "name": f"low-mccs/tile/{tpm_1_number:04}",
            "subscriptions": [
                "adminMode",
                "state",
                "tileProgrammingState",
            ],
        },
        "tile_2": {
            "name": f"low-mccs/tile/{tpm_2_number:04}",
            "subscriptions": [
                "adminMode",
                "state",
                "tileProgrammingState",
            ],
        },
        "DAQ": {
            "name": "low-mccs/daqreceiver/001",
            "subscriptions": [
                "adminMode",
                "state",
            ],
        },
    }


@pytest.fixture(name="get_device", scope="session")
def get_device_fixture(
    tango_context: TangoContextProtocol,
    device_mapping: dict[str, DeviceMapping],
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Callable[[str], tango.DeviceProxy]:
    """
    Return a memoized function that returns a DeviceProxy for a given name.

    :param tango_context: a TangoContextProtocol to instantiate DeviceProxys
    :param device_mapping: a map from short to canonical device names
    :param change_event_callbacks: dictionary of mock change event
        callbacks with asynchrony support

    :return: a memoized function that takes a name and returns a DeviceProxy
    """

    @lru_cache
    def _get_device(short_name: str) -> tango.DeviceProxy:
        device_data = device_mapping[short_name]
        name = device_data["name"]
        tango_device = tango_context.get_device(name)

        # TODO: why do some devices i.e. MccsDaqReceiver need this?
        for _ in range(23):
            try:
                device_info = tango_device.info()
                break
            except tango.DevFailed:
                time.sleep(5)
        else:
            device_info = tango_device.info()

        dev_class = device_info.dev_class
        print(f"Created DeviceProxy for {short_name} - {dev_class} {name}")
        time.sleep(5)
        for attr in device_data.get("subscriptions", []):
            attr_value = tango_device.read_attribute(attr).value
            attr_event = change_event_callbacks[f"{name}/{attr}"]
            tango_device.subscribe_event(
                attr,
                tango.EventType.CHANGE_EVENT,
                attr_event,
            )
            print(f"Subscribed to {name}/{attr}")
            if not isinstance(attr_value,int) and not isinstance(attr_value,str) and attr_value is not None:
                attr_value = list(attr_value)
            change_event_callbacks.assert_change_event(f"{name}/{attr}",attr_value,lookahead=20)
            print(f"Received initial value for {name}/{attr}: {attr_value}")

        return tango_device

    return _get_device

def expect_attribute(
    tango_device: tango.DeviceProxy,
    attr: str,
    value: Any,
    *,
    timeout: float = 60.0,
) -> bool:
    """
    Wait for Tango attribute to have a certain value using a subscription.

    Sets up a subscription to a Tango device attribute,
    waits for the attribute to have the provided value within a given time,
    then removes the subscription.

    :param tango_device: a DeviceProxy to a Tango device
    :param attr: the name of the attribute to be monitored
    :param value: the attribute value we're waiting for
    :param timeout: the maximum time to wait, in seconds
    :return: True if the attribute has the expected value within the given timeout
    """
    print(f"Expecting {tango_device.dev_name()}/{attr} == {value!r} within {timeout}s")
    _queue: queue.SimpleQueue[tango.EventData] = queue.SimpleQueue()
    subscription_id = tango_device.subscribe_event(
        attr,
        tango.EventType.CHANGE_EVENT,
        _queue.put,
    )
    deadline = time.time() + timeout
    try:
        while True:
            event = _queue.get(timeout=deadline - time.time())
            print(f"Got {tango_device.dev_name()}/{attr} == {event.attr_value.value!r}")
            if event.attr_value.value == value:
                return True
    finally:
        tango_device.unsubscribe_event(subscription_id)


def wait_attribute(
    tango_device: tango.DeviceProxy,
    attr: str,
    value: Any,
    *,
    timeout: float = 60.0,
) -> bool:
    """
    Poll a Tango attribute, up to a timeout, until it has the given value.

    If the attribute supports subscriptions, use expect_attribute instead.

    :param tango_device: a DeviceProxy to a Tango device
    :param attr: the name of the attribute to be monitored
    :param value: the attribute value we're waiting for
    :param timeout: the maximum time to wait, in seconds
    :return: True if the attribute has the expected value within the given timeout
    """
    print(
        f"Polling for {tango_device.dev_name()}/{attr} == {value!r} within {timeout}s"
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        current_value = tango_device.read_attribute(attr).value
        print(f"Got {tango_device.dev_name()}/{attr} == {current_value!r}")
        if current_value == value:
            return True
        time.sleep(1.0)
    return False


def _str_to_tango(attr: tango.AttributeInfoEx, value: str) -> Any:
    """
    Convert a str to a type compatible with the given Tango attribute.

    :param attr: metadata about the attribute being compared against
    :param value: a string value from a parametrised BDD step
    :return: a value that can be compared to the attribute's value
    """
    print(f"coerceing value {value} for attr {attr.name}")
    retval: Any
    if attr.data_type in [
        tango.ArgType.DevLong,
        tango.ArgType.DevLong64,
        tango.ArgType.DevShort,
        tango.ArgType.DevULong,
        tango.ArgType.DevULong64,
        tango.ArgType.DevUShort,
    ]:
        retval = int(value)

    elif attr.data_type in [
        tango.ArgType.DevDouble,
        tango.ArgType.DevFloat,
    ]:
        retval = float(value)

    elif attr.data_type == tango.ArgType.DevBoolean:
        retval = value in ["True", "true"]

    elif attr.data_type == tango.ArgType.DevState:
        retval = getattr(tango.DevState, value)

    elif attr.data_type == tango.ArgType.DevEnum:
        # StdStrVector doesn't have an index() method
        retval = next(
            (i for i, v in enumerate(attr.enum_labels) if v == value),
            object(),  # nothing will have this value
        )
    elif attr.data_type == tango.ArgType.DevString:
        retval = value
    else:
        print(f"Couldn't coerce {repr(value)}")
        retval = value
    return retval


_DevState = {"ON": tango.DevState.ON, "OFF": tango.DevState.OFF, "STANDBY": tango.DevState.STANDBY}.__getitem__


@given(
    parsers.parse("a {short_name} that is in mode {mode} and state {state}"),
    converters={
        "state": _DevState,
        "mode": AdminMode.__getitem__,
    },
)
def get_online_tango_device(
    change_event_callbacks: MockTangoEventCallbackGroup,
    get_device: Callable[[str], tango.DeviceProxy],
    short_name: str,
    mode: AdminMode,
    state: tango.DevState,
    device_mapping: dict[str, DeviceMapping],
) -> tango.DeviceProxy:
    """
    Given a short name, get a Tango device in the given state and mode.

    :param change_event_callbacks: dictionary of mock change event
        callbacks with asynchrony support
    :param get_device: a caching Tango device factory
    :param short_name: the short name for the Tango device
    :param mode: the desired AdminMode
    :param state: the desired DevState
    :return: a Tango DeviceProxy to a device in the desired state
    """
    dev = get_device(short_name)
    dev_name = dev.dev_name()

    initial_admin_mode = dev.read_attribute("adminMode").value
    admin_mode_events = change_event_callbacks[f"{dev_name}/adminMode"]

    initial_state = dev.read_attribute("state").value
    state_events = change_event_callbacks[f"{dev_name}/state"]

    # assert that state is what it should be given the AdminMode
    if initial_admin_mode in {AdminMode.ONLINE, AdminMode.MAINTENANCE}:
        # TODO: TPM simulator sometimes goes into ALARM due to MIN CURRENT
        assert initial_state in {
            tango.DevState.OFF,
            tango.DevState.ALARM,
            tango.DevState.ON,
            tango.DevState.UNKNOWN
        }
    else:  # AdminMode OFFLINE, NOT_FITTED, RESERVED
        assert initial_state == tango.DevState.DISABLE

    # only support ONLINE for now
    #assert mode == AdminMode.ONLINE

    dev.adminmode = mode
    # bring ONLINE if not already
    if initial_admin_mode != mode:
        dev.adminMode = mode
        admin_mode_events.assert_change_event(mode)

        if initial_admin_mode == mode:
            state_events.assert_not_called()
        else:
            # TODO: MccsTile should transition to UNKNOWN but doesn't
            # if dev.info().dev_class != "MccsTile":
            state_events.assert_change_event(tango.DevState.UNKNOWN)
            state_events.assert_change_event(
                OneOf(tango.DevState.ON, tango.DevState.OFF, tango.DevState.STANDBY, tango.DevState.UNKNOWN),lookahead=50
            )

    # should we be on or off?
    if dev.read_attribute("state").value != state:
        print(f"Turning {dev.dev_name()} {state}")
        set_tango_device_state(change_event_callbacks, get_device, short_name, state)

    return dev


@given(parsers.parse("the {device}'s {attribute} is set to {value}"))
@when(parsers.parse("the {device}'s {attribute} is set to {value}"))
def set_tango_device_attribute(
    get_device: Callable[[str], tango.DeviceProxy],
    device: str,
    attribute: str,
    value: str,
) -> None:
    """
    Set a Tango device's attribute to the given value.

    Write the attribute value using DeviceProxy.write_attribute, and confirm that it
    takes that value using expect_attribute. Before writing the value, it's converted
    to the correct Tango type based on the attribute's metadata.

    :param get_device: a caching Tango device factory
    :param device: the short name for the Tango device
    :param attribute: the name of the attribute to be written
    :param value: the value to write to the attribute
    """
    dev = get_device(device)
    attr_config = dev.attribute_query(attribute)
    tango_value = _str_to_tango(attr_config, value)
    dev.write_attribute(attribute, tango_value)
    expect_attribute(dev, attribute, tango_value)


@when(
    parsers.parse("the user turns the {short_name} {desired_state}"),
    converters={"desired_state": _DevState},
)
def set_tango_device_state(
    change_event_callbacks: MockTangoEventCallbackGroup,
    get_device: Callable[[str], tango.DeviceProxy],
    short_name: str,
    desired_state: tango.DevState,
) -> None:
    """
    Turn a Tango device on or off using its On() and Off() commands.

    :param change_event_callbacks: dictionary of mock change event
        callbacks with asynchrony support
    :param get_device: a caching Tango device factory
    :param short_name: the short name of the device
    :param desired_state: the desired power state, either "on" or "off"
    """
    dev = get_device(short_name)
    # Issue the command
    if desired_state == tango.DevState.ON:
        [result_code], [command_id] = dev.On()
    elif desired_state == tango.DevState.OFF:
        [result_code], [command_id] = dev.Off()
    elif desired_state == tango.DevState.STANDBY:
        [result_code], [command_id] = dev.Standby()
    else:
        raise ValueError(f"State {desired_state} is not a valid state.")

    assert result_code == ResultCode.QUEUED
    print(f"Command queued on {dev.dev_name()}: {command_id}")

    # while not (
    #     result_code == "COMPLETED"
    #     or (
    #         # status to FAILED even when it succeeds in turning its TPM on
    #         dev.info().dev_class == "MccsTile"
    #         and result_code == "FAILED"
    #     )
    # ):
    #     call_details = change_event_callbacks[
    #         f"{dev.dev_name()}/longRunningCommandStatus"
    #     ].assert_against_call()
    #     print(f"LRCS on {dev.dev_name()}: {call_details['attribute_value']}")
    #     assert call_details["attribute_value"][-2] == command_id
    #     result_code = call_details["attribute_value"][-1]

    change_event_callbacks[f"{dev.dev_name()}/state"].assert_change_event(desired_state)


@then(parsers.parse("the {device}'s {attribute} is {value}"))
def check_tango_device_attribute_value(
    get_device: Callable[[str], tango.DeviceProxy],
    device: str,
    attribute: str,
    value: str,
) -> None:
    """
    Check that a Tango attribute has a particular value.

    :param get_device: a caching Tango device factory
    :param device: short device name
    :param attribute: the name of the attribute to check
    :param value: the attribute value to assert against
    """
    dev = get_device(device)
    attr_config = dev.attribute_query(attribute)
    cmp_value = _str_to_tango(attr_config, value)
    print(f"value: {value}\ncoerced: {cmp_value}")
    attr = dev.read_attribute(attribute)
    print(f"{dev.dev_name()}/{attribute}:")
    print(attr)
    assert attr.value == cmp_value


# TODO: see comment below - can't make timeout optional without fixing pytest-bdd
# @then(parsers.parse("the {device}'s {attribute} becomes {value}"))
@then(parsers.parse("the {device}'s {attribute} becomes {value} within {timeout:g}s"))
def check_tango_device_attribute_change_event_timeout(
    get_device: Callable[[str], tango.DeviceProxy],
    device: str,
    attribute: str,
    value: str,
    timeout: float,  # setting a default over overrides any parsed value
) -> None:
    """
    Watch Tango attribute change events until an expected value is seen.

    :param get_device: a caching Tango device factory
    :param device: short device name
    :param attribute: the name of the attribute to check
    :param value: the attribute value to assert against
    :param timeout: how long to wait for the attribute value to change
    """
    dev = get_device(device)

    attr_meta = dev.attribute_query(attribute)
    cmp_value = _str_to_tango(attr_meta, value)

    assert expect_attribute(dev, attribute, cmp_value, timeout=timeout)


@then(
    parsers.parse("the {device} reports that it is {state}"),
    converters={"state": _DevState},
)
def check_tango_device_state(
    get_device: Callable[[str], tango.DeviceProxy],
    device: str,
    state: tango.DevState,
) -> None:
    """
    Check that a device is in a given DevState.

    :param get_device: a caching Tango device factory
    :param device: short device name
    :param state: the expected tango.DevState value
    """
    dev = get_device(device)
    assert dev.read_attribute("state").value == state

