# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the daq configuration."""
from __future__ import annotations

from typing import Iterator

import pytest
import tango
from pytest_bdd import given, parsers, scenario, then, when
from ska_control_model import AdminMode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from tests.harness import SpsTangoTestHarnessContext

EXTRA_TYPES = {
    "Dict": str,
}


@scenario(
    "features/daq_configuration.feature",
    "Check that DAQ can be configured",
)
def test_daq_configuration() -> None:
    """
    Test DAQ configuration handling.

    Check that when a configuration is sent to the MccsDaqReceiver,
    the DAQ_receiver interface is configured correctly.

    Any code in this scenario method is run at the *end* of the
    scenario.
    """


@given("A MccsDaqReceiver is available", target_fixture="daq_receiver")
def given_a_daq_receiver(
    functional_test_context: SpsTangoTestHarnessContext,
    daq_id: int,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> Iterator[tango.DeviceProxy]:
    """
    Yield the DAQ receiver device under test.

    :param functional_test_context: the context in which the test is running.
    :param daq_id: the ID of the daq receiver
    :param change_event_callbacks: A change event callback group.

    :yield: the DAQ receiver device
    """
    daq_receiver = functional_test_context.get_daq_device(daq_id)

    daq_receiver.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["daq_state"],
    )

    admin_mode = daq_receiver.adminMode
    if admin_mode == AdminMode.OFFLINE:
        change_event_callbacks.assert_change_event("daq_state", tango.DevState.DISABLE)

        daq_receiver.adminMode = AdminMode.ONLINE
        change_event_callbacks.assert_change_event("daq_state", tango.DevState.UNKNOWN)
        change_event_callbacks.assert_change_event("daq_state", tango.DevState.ON)

    yield daq_receiver


@when("We pass a configuration to the MccsDaqReceiver")
def feed_daq_configuration_file(daq_receiver: tango.DeviceProxy) -> None:
    """
    Feed the configuration into the daq_receiver.

    :param daq_receiver: The daq_receiver fixture to use.
    """
    pytest.xfail(reason="Not ready")
    # MccsDaqReceiver expects a string as input, this will be a string representation
    # of a dictionary.
    # daq_receiver.Configure(configuration)


@then("The DAQ_receiver interface has the expected configuration")
def assert_daq_instance_is_configured_correctly(
    daq_receiver: tango.DeviceProxy,
) -> None:
    """
    Assert daq_instance has the same configuration that we sent to the daq_receiver.

    :param daq_receiver: The daq_receiver fixture to use.

    Notes: we may only send a subset of the configuration to the DaqInstance.
    """
    pytest.xfail(reason="Not ready")
    # configuration_dict = json.loads(configuration_expected)

    # config_jstr = daq_receiver.GetConfiguration()
    # retrieved_daq_config = json.loads(config_jstr)

    # assert configuration_dict.items() <= retrieved_daq_config.items()


@when(
    parsers.cfparse(
        (
            "We pass parameter {configuration_param:w} of value {value:w} "
            "to the MccsDaqReceiver"
        ),
        extra_types=EXTRA_TYPES,
    )
)
def pass_key_value_to_daq(
    daq_receiver: tango.DeviceProxy, configuration_param: str, value: str
) -> None:
    """
    Pass a string representation of a dictionary to MccsDaqReceiver.

    :param daq_receiver: The daq_receiver fixture to use.
    :param configuration_param: The parameter of interest
    :param value: The value of that parameter
    """
    pytest.xfail(reason="Not ready")
    # # could not find a way to pass in ""
    # so i have passed "None" and converted it here.
    # if value == "None":
    #     value = ""

    # configuration = f'{{"{configuration_param}":{value}}}'

    # # configure DAQ using the string representation of a dictionary
    # daq_receiver.Configure(configuration)


@then(
    parsers.cfparse(
        "The DAQ receiver interface has a valid {receiver_ip:w}",
        extra_types=EXTRA_TYPES,
    )
)
def check_response_as_expected(
    daq_receiver: tango.DeviceProxy, receiver_ip: str
) -> None:
    """
    Specific parameters passed to the daq_receiver_interface are overridden.

    :param daq_receiver: The daq_receiver fixture to use.
    :param receiver_ip: The parameter of interest

    If the ip is not assigned it is assigned the IP address of a specified interface
    'receiver_interface'. This tests that the value has changed.
    TODO: determine what other values are allowed
    """
    pytest.xfail(reason="Not ready")
    # daq_config_jstr = daq_receiver.GetConfiguration()
    # retrieved_daq_config = json.loads(daq_config_jstr)
    # receiver_port = retrieved_daq_config[receiver_ip]

    # try:
    #     socket.inet_aton(receiver_port)
    # except IOError:
    #     # the ip address is not valid
    #     pytest.fail("Invalid IP address causes IOError")