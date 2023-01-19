# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains pytest-specific test harness for MCCS unit tests."""
from typing import ContextManager, Generator

import pytest
from _pytest.fixtures import SubRequest
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
    TrueTangoContextManager,
)


def pytest_itemcollected(item: pytest.Item) -> None:
    """
    Modify a test after it has been collected by pytest.

    This pytest hook implementation adds the "forked" custom mark to all
    tests that use the ``tango_harness`` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    """
    if "tango_harness" in item.fixturenames:  # type: ignore[attr-defined]
        item.add_marker("forked")


# @pytest.fixture(name="subrack", scope="session")
# def subrack_fixture() -> str:
#     """
#     Return the daq id of this subrack.
# 
#     :return: the daq id of this daq receiver.
#     """
#     # TODO: This must match the DaqId property of the daq receiver under
#     # test. We should refactor the harness so that we can pull it
#     # straight from the device configuration.
#     return "1"
# 
# 
# @pytest.fixture(name="receiver_interface", scope="session")
# def receiver_interface_fixture() -> str:
#     """
#     Return the interface this daq receiver is watching.
# 
#     :return: the interface this daq receiver is watching.
#     """
#     return "eth0"
# 
# 
# @pytest.fixture(name="receiver_ip", scope="session")
# def receiver_ip_fixture() -> str:
#     """
#     Return the ip of this daq receiver.
# 
#     :return: the ip of this daq receiver.
#     """
#     return "172.17.0.230"
# 
# 
# @pytest.fixture(name="acquisition_duration", scope="session")
# def acquisition_duration_fixture() -> int:
#     """
#     Return the duration of data capture in seconds.
# 
#     :return: Duration of data capture.
#     """
#     return 2
# 
# 
# @pytest.fixture(name="receiver_ports", scope="session")
# def receiver_ports_fixture() -> str:
#     """
#     Return the port(s) this daq receiver is watching.
# 
#     :return: the port(s) this daq receiver is watching.
#     """
#     return "4660"
# 
# 
# @pytest.fixture()
# def default_consumers_to_start() -> str:
#     """
#     Return an empty string.
# 
#     :return: An empty string.
#     """
#     return ""
# 
# 
# @pytest.fixture()
# def max_workers() -> int:
#     """
#     Max worker threads available to run a LRC.
# 
#     Return an integer specifying the maximum number of worker threads available to
#         execute long-running-commands.
# 
#     :return: the max number of worker threads.
#     """
#     return 1


@pytest.fixture(scope="session", name="testbed")
def testbed_fixture(request: SubRequest) -> str:
    """
    Return the name of the testbed.

    The testbed is specified by providing the `--testbed` argument to
    pytest. Information about what testbeds are supported and what tests
    can be run in each testbed is provided in `testbeds.yaml`

    :param request: A pytest object giving access to the requesting test
        context.

    :return: the name of the testbed.
    """
    return request.config.getoption("--testbed")


# @pytest.fixture(name="daq_name", scope="session")
# def daq_name_fixture(daq_id: str) -> str:
#     """
#     Return the name of this daq receiver.
# 
#     :param daq_id: The ID of this daq receiver.
# 
#     :return: the name of this daq receiver.
#     """
#     return f"low-mccs-daq/daqreceiver/{daq_id.zfill(3)}"


@pytest.fixture(name="tango_harness", scope="session")
def tango_harness_fixture(
    testbed: str,
#     daq_name: str,
#     daq_id: str,
#     receiver_interface: str,
#     receiver_ip: str,
#     receiver_ports: str,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param testbed: the name of the testbed to which these tests are
        deployed
    :param daq_name: name of the DAQ receiver Tango device
    :param daq_id: id of the DAQ receiver
    :param receiver_interface: network interface on which the DAQ
        receiver receives packets
    :param receiver_ip: IP address on which the DAQ receiver receives
        packets
    :param receiver_ports: port on which the DAQ receiver receives
        packets.

    :raises ValueError: if the testbed is unknown

    :yields: a tango context.
    """
    context_manager: ContextManager[TangoContextProtocol]
    if testbed == "local":
        context_manager = TrueTangoContextManager()
    elif testbed == "test":
        context_manager = ThreadedTestTangoContextManager()
        context_manager.add_device(
            "low-mccs/subrack/01",
            "ska_low_mccs_spshw.MccsSubrack",
        )
        context_manager.add_device(
            "low-mccs/tile/0001",
            "ska_low_mccs_spshw.MccsTile",
            SubrackFQDN = "low-mccs/subrack/01",
            SubrackBay = 1,
        )
    else:
        raise ValueError(f"Testbed {testbed} is not supported.")

    with context_manager as context:
        yield context

# # -*- coding: utf-8 -*-
# #
# # This file is part of the SKA Low MCCS project
# #
# #
# # Distributed under the terms of the BSD 3-clause new license.
# # See LICENSE for more info.
# """This module contains pytest-specific test harness for PaSD functional tests."""
# import unittest
# from typing import Any, Callable, Generator
# 
# import pytest
# from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness
# 
# 
# @pytest.fixture(scope="function")
# def tango_config() -> dict[str, Any]:
#     """
#     Fixture that returns basic configuration information for a Tango test harness.
# 
#     e.g. such as whether or not to run in a separate process.
# 
#     :return: a dictionary of configuration key-value pairs
#     """
#     return {"process": True}
# 
# 
# @pytest.fixture(scope="function")
# def tango_harness(
#     tango_harness_factory: Callable[
#         [
#             dict[str, Any],
#             DevicesToLoadType,
#             Callable[[], unittest.mock.Mock],
#             dict[str, unittest.mock.Mock],
#         ],
#         TangoHarness,
#     ],
#     tango_config: dict[str, str],
#     devices_to_load: DevicesToLoadType,
#     mock_factory: Callable[[], unittest.mock.Mock],
#     initial_mocks: dict[str, unittest.mock.Mock],
# ) -> Generator[TangoHarness, None, None]:
#     """
#     Create a test harness for testing Tango devices.
# 
#     (This overwrites the `tango_harness` fixture, in order to change the
#     fixture scope.)
# 
#     :param tango_harness_factory: a factory that provides a test harness
#         for testing tango devices
#     :param tango_config: basic configuration information for a tango
#         test harness
#     :param devices_to_load: fixture that provides a specification of the
#         devices that are to be included in the devices_info dictionary
#     :param mock_factory: the factory to be used to build mocks
#     :param initial_mocks: a pre-build dictionary of mocks to be used
#         for particular
# 
#     :yields: the test harness
#     """
#     with tango_harness_factory(
#         tango_config, devices_to_load, mock_factory, initial_mocks
#     ) as harness:
#         yield harness
