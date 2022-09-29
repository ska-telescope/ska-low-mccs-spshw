# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of MCCS power management functionality."""
from __future__ import annotations

import time
import unittest.mock

import pytest
from ska_tango_base.control_model import AdminMode
from tango import DevState

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.testing.mock import MockDeviceBuilder
from ska_low_mccs.testing.tango_harness import DevicesToLoadType, TangoHarness


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "apiu_001", "proxy": MccsDeviceProxy},
            {"name": "antenna_000001", "proxy": MccsDeviceProxy},
            #             {"name": "antenna_000002", "proxy": MccsDeviceProxy},
            #             {"name": "antenna_000003", "proxy": MccsDeviceProxy},
            #             {"name": "antenna_000004", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def mock_tile() -> unittest.mock.Mock:
    """
    Return a mock tile device for use in testing.

    The mock device will mock a powered-on tile.

    :return: a mock tile device for use in testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(DevState.ON)
    return builder()


@pytest.fixture()
def initial_mocks(
    mock_tile: unittest.mock.Mock,
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_tile: a mock tile device to be injected into the Tango
        test harness

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/tile/0001": mock_tile,
    }


class TestApiuAntennaIntegration:
    """Integration test cases for interactions between APIU and antenna."""

    def test_apiu_antenna_integration(
        self: TestApiuAntennaIntegration, tango_harness: TangoHarness
    ) -> None:
        """
        Test the integration of antenna within the APIU.

        Test that:

        * when MccsAntenna is turned on, the APIU supplies power to the
          antenna
        * when MccsAntenna is turned off, the APIU denies power to the
          antenna

        :param tango_harness: a test harness for tango devices
        """
        antenna_device = tango_harness.get_device("low-mccs/antenna/000001")
        apiu_device = tango_harness.get_device("low-mccs/apiu/001")
        mock_tile_device = tango_harness.get_device("low-mccs/tile/0001")

        # The factory default adminMode is OFFLINE, which means the device does not try
        # to establish communication with its component, and remains in DISABLE state.
        # Usually it will only do so for a very short time, until the memorized value
        # adminMode is written.
        # We haven't provided a memorized value for adminMode, so these devices
        # initialise to DISABLE state...
        time.sleep(2)
        state = antenna_device.state()
        assert state == DevState.DISABLE
        state = apiu_device.state()
        assert state == DevState.DISABLE

        # ... except for the tile device, which is mocked to always be in ON state
        assert mock_tile_device.state() == DevState.ON

        antenna_device.adminMode = AdminMode.ONLINE
        # The antenna device tries to establish communication with its antenna. To do
        # that it has to go through its APIU and its Tile.
        # So it creates proxies to the APIU and Tile devices.
        # The first thing it needs to know is whether those devices are turned on, so it
        # subscribes to change events on device state. There's nothing more to do until
        # it receives those change events, so it transitions to UNKNOWN (since it is now
        # trying to establish communication with its antenna) and returns.
        # time.sleep(0.2)
        # assert antenna_device.state() == DevState.UNKNOWN

        # The tile device sends an event advising that it is ON, and the APIU device
        # sends an event advising that it is DISABLE.
        time.sleep(0.2)
        # The antenna device receives these events, and realises that it can't establish
        # communication with its antenna through an APIU device that isn't even
        # monitoring its APIU.
        # The antenna device doesn't FAULT, or time-out, or enter a backoff-retry loop.
        # It simply remains in UNKNOWN state, waiting for the next event.
        assert antenna_device.state() == DevState.ON

        apiu_device.adminMode = AdminMode.ONLINE
        # The APIU device establishes communication with its APIU. It finds that the
        # APIU is turned off, so it transitions to OFF...
        time.sleep(0.2)
        assert apiu_device.state() == DevState.OFF

        # ... and fires a change event...
        time.sleep(0.1)
        # ... which is received by the antenna device. Since the event indicates that
        # the APIU hardware is OFF, the antenna device has established that its antenna
        # is not powered, so it transitions to OFF state.
        assert antenna_device.state() == DevState.OFF

        apiu_device.On()
        # The APIU device tells the APIU hardware to power on. Once the APIU hardware
        # has powered on, the APIU device detects that change of state, and transitions
        # to ON state.
        time.sleep(0.2)
        assert apiu_device.state() == DevState.ON

        # It fires a change event...
        time.sleep(0.1)
        # ...which is received by the antenna device.

        # The antenna device subscribes to change events on the power mode of the
        # antennas managed by the APIU. The APIU device knows that the antenna is off...
        assert not apiu_device.isAntennaOn(1)
        # ... and fires a change event...
        time.sleep(0.1)
        # ... which is received by the antenna. The antenna device now knows that its
        # antenna is powered off, so it stays in state OFF.
        assert antenna_device.state() == DevState.OFF

        antenna_device.On()

        # The antenna device tells the antenna to turn on. It does this by telling the
        # APIU device to tell its APIU hardware to turn on antenna 1.
        # The APIU device does so, and then detects that antenna 1 is on.
        time.sleep(0.1)

        assert apiu_device.IsAntennaOn(1)
        # It fires a change event which is received by the antenna device. The antenna device now knows that
        # its antenna is powered on, so it transitions to state ON.
        time.sleep(0.1)
        assert antenna_device.state() == DevState.ON

        apiu_device.PowerDownAntenna(1)
        # A third party has told the APIU device to turn the antenna off.
        # The APIU device tells its APIU to turn the antenna off.
        # Once it is off, the APIU device detects that the antenna is off...
        time.sleep(0.1)
        assert not apiu_device.IsAntennaOn(1)

        # ... and fires a change event...
        time.sleep(0.2)
        # ... which is received by the antenna device. The antenna device now knows that
        # its antenna is powered off, so it transitions to state OFF.
        assert antenna_device.state() == DevState.OFF
