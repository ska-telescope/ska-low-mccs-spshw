# type: ignore
# pylint: skip-file
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains tests of pointing interactions between devices."""
from __future__ import annotations

import time
import unittest.mock
from typing import Callable

import pytest
import tango
from ska_control_model import AdminMode, ResultCode
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockDeviceBuilder
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness

# some constants to refer to in the tests
BEAM_1_ID = 1
BEAM_1_DELAY_AZIMUTH = 1.0e-9
BEAM_1_DELAY_ELEVATION = 1.0e-9
BEAM_1_DELAY_RATE_AZIMUTH = 0.1e-11
BEAM_1_DELAY_RATE_ELEVATION = 0.1e-11
BEAM_2_ID = 2
BEAM_2_DELAY_AZIMUTH = 2.0e-9
BEAM_2_DELAY_ELEVATION = 2.0e-9
BEAM_2_DELAY_RATE_AZIMUTH = 0.2e-11
BEAM_2_DELAY_RATE_ELEVATION = 0.2e-11
BEAM_3_ID = 3
BEAM_3_DELAY_AZIMUTH = 3.0e-9
BEAM_3_DELAY_ELEVATION = 3.0e-9
BEAM_3_DELAY_RATE_AZIMUTH = 0.3e-11
BEAM_3_DELAY_RATE_ELEVATION = 0.3e-11
BEAM_4_ID = 4
BEAM_4_DELAY_AZIMUTH = 4.0e-9
BEAM_4_DELAY_ELEVATION = 4.0e-9
BEAM_4_DELAY_RATE_AZIMUTH = 0.4e-11
BEAM_4_DELAY_RATE_ELEVATION = 0.4e-11


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved, we
    # should reinstate the APIUs and antennas in these tests.
    return {
        "path": "tests/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "beam_01", "proxy": MccsDeviceProxy},
            {"name": "beam_02", "proxy": MccsDeviceProxy},
            {"name": "beam_03", "proxy": MccsDeviceProxy},
            {"name": "beam_04", "proxy": MccsDeviceProxy},
        ],
    }


@pytest.fixture()
def mock_apiu_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock APIU devices for use in testing.

    Each mock device will mock a powered-on APIU.

    :return: a factory that returns a mock APIU device for use in
        testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    return builder


@pytest.fixture()
def mock_antenna_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock antenna device for use in testing.

    Each mock device will mock a powered-on antenna.

    :return: a mock APIU device for use in testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    return builder


@pytest.fixture()
def mock_tile_factory() -> Callable[[], unittest.mock.Mock]:
    """
    Return a factory that returns mock tile devices for use in testing.

    Each mock device will mock a powered-on tile.

    :return: a mock tile device for use in testing.
    """
    builder = MockDeviceBuilder()
    builder.set_state(tango.DevState.ON)
    builder.add_result_command("SetPointingDelay", ResultCode.OK)
    return builder


@pytest.fixture()
def initial_mocks(
    mock_apiu_factory: Callable[[], unittest.mock.Mock],
    mock_antenna_factory: Callable[[], unittest.mock.Mock],
    mock_tile_factory: Callable[[], unittest.mock.Mock],
) -> dict[str, unittest.mock.Mock]:
    """
    Return a specification of the mock devices to be set up in the Tango test harness.

    This is a pytest fixture that can be used to inject pre-build mock
    devices into the Tango test harness at specified FQDNs.

    :param mock_apiu_factory: a factory that returns a mock apiu device
    :param mock_antenna_factory: a factory that returns a mock antenna
        device
    :param mock_tile_factory: a factory that returns a mock tile device

    :return: specification of the mock devices to be set up in the Tango
        test harness.
    """
    return {
        "low-mccs/apiu/001": mock_apiu_factory(),
        "low-mccs/apiu/002": mock_apiu_factory(),
        "low-mccs/antenna/000001": mock_antenna_factory(),
        "low-mccs/antenna/000002": mock_antenna_factory(),
        "low-mccs/antenna/000003": mock_antenna_factory(),
        "low-mccs/antenna/000004": mock_antenna_factory(),
        "low-mccs/antenna/000005": mock_antenna_factory(),
        "low-mccs/antenna/000006": mock_antenna_factory(),
        "low-mccs/antenna/000007": mock_antenna_factory(),
        "low-mccs/antenna/000008": mock_antenna_factory(),
        "low-mccs/tile/0001": mock_tile_factory(),
        "low-mccs/tile/0002": mock_tile_factory(),
        "low-mccs/tile/0003": mock_tile_factory(),
        "low-mccs/tile/0004": mock_tile_factory(),
    }


class TestMccsIntegration:
    """Integration test cases for the Mccs device classes."""

    def test_stationbeam_apply_pointing(
        self: TestMccsIntegration, tango_harness: TangoHarness
    ) -> None:
        """
        Test that a MccsStationBeam can apply delays to associated MccsTiles.

        :param tango_harness: a test harness for tango devices
        """
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        stationbeam_1 = tango_harness.get_device("low-mccs/beam/01")
        stationbeam_2 = tango_harness.get_device("low-mccs/beam/02")
        stationbeam_3 = tango_harness.get_device("low-mccs/beam/03")
        stationbeam_4 = tango_harness.get_device("low-mccs/beam/04")
        mock_tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        mock_tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        mock_tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        mock_tile_4 = tango_harness.get_device("low-mccs/tile/0004")

        stationbeam_1.adminMode = AdminMode.ONLINE
        stationbeam_2.adminMode = AdminMode.ONLINE
        stationbeam_3.adminMode = AdminMode.ONLINE
        stationbeam_4.adminMode = AdminMode.ONLINE
        station_1.adminMode = AdminMode.ONLINE
        station_2.adminMode = AdminMode.ONLINE

        time.sleep(0.1)

        stationbeam_1.pointingDelay = [
            BEAM_1_DELAY_AZIMUTH,
            BEAM_1_DELAY_ELEVATION,
        ]
        stationbeam_2.pointingDelay = [
            BEAM_2_DELAY_AZIMUTH,
            BEAM_2_DELAY_ELEVATION,
        ]
        stationbeam_3.pointingDelay = [
            BEAM_3_DELAY_AZIMUTH,
            BEAM_3_DELAY_ELEVATION,
        ]
        stationbeam_4.pointingDelay = [
            BEAM_4_DELAY_AZIMUTH,
            BEAM_4_DELAY_ELEVATION,
        ]
        stationbeam_1.pointingDelayRate = [
            BEAM_1_DELAY_RATE_AZIMUTH,
            BEAM_1_DELAY_RATE_ELEVATION,
        ]
        stationbeam_2.pointingDelayRate = [
            BEAM_2_DELAY_RATE_AZIMUTH,
            BEAM_2_DELAY_RATE_ELEVATION,
        ]
        stationbeam_3.pointingDelayRate = [
            BEAM_3_DELAY_RATE_AZIMUTH,
            BEAM_3_DELAY_RATE_ELEVATION,
        ]
        stationbeam_4.pointingDelayRate = [
            BEAM_4_DELAY_RATE_AZIMUTH,
            BEAM_4_DELAY_RATE_ELEVATION,
        ]

        # states are ON because we haven't assigned a station
        assert stationbeam_1.state() == tango.DevState.ON
        assert stationbeam_2.state() == tango.DevState.ON
        assert stationbeam_3.state() == tango.DevState.ON
        assert stationbeam_4.state() == tango.DevState.ON

        # allocate does not currently include station_beams, so assigning manually
        stationbeam_1.stationFqdn = "low-mccs/station/001"
        stationbeam_1.logicalBeamId = BEAM_1_ID
        stationbeam_2.stationFqdn = "low-mccs/station/001"
        stationbeam_2.logicalBeamId = BEAM_2_ID
        stationbeam_3.stationFqdn = "low-mccs/station/002"
        stationbeam_3.logicalBeamId = BEAM_3_ID
        stationbeam_4.stationFqdn = "low-mccs/station/002"
        stationbeam_4.logicalBeamId = BEAM_4_ID

        time.sleep(0.1)

        assert stationbeam_1.state() == tango.DevState.ON
        assert stationbeam_2.state() == tango.DevState.ON
        assert stationbeam_3.state() == tango.DevState.ON
        assert stationbeam_4.state() == tango.DevState.ON

        # stations are on because we have mocked all their components to be on
        assert station_1.state() == tango.DevState.ON
        assert station_2.state() == tango.DevState.ON

        ([result_code], _) = stationbeam_1.ApplyPointing()
        assert result_code == ResultCode.QUEUED

        # we need to do this the long way because if Tango is numpy-enabled, then the
        # component manager will be called with an array not a list.
        (args, kwargs) = mock_tile_1.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_1_ID),
            BEAM_1_DELAY_AZIMUTH,
            BEAM_1_DELAY_RATE_AZIMUTH,
            BEAM_1_DELAY_ELEVATION,
            BEAM_1_DELAY_RATE_ELEVATION,
        ]

        (args, kwargs) = mock_tile_2.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_1_ID),
            BEAM_1_DELAY_AZIMUTH,
            BEAM_1_DELAY_RATE_AZIMUTH,
            BEAM_1_DELAY_ELEVATION,
            BEAM_1_DELAY_RATE_ELEVATION,
        ]
        mock_tile_3.SetPointingDelay.assert_not_called()
        mock_tile_4.SetPointingDelay.assert_not_called()

        ([result_code], _) = stationbeam_2.ApplyPointing()
        assert result_code == ResultCode.QUEUED

        (args, kwargs) = mock_tile_1.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_2_ID),
            BEAM_2_DELAY_AZIMUTH,
            BEAM_2_DELAY_RATE_AZIMUTH,
            BEAM_2_DELAY_ELEVATION,
            BEAM_2_DELAY_RATE_ELEVATION,
        ]

        (args, kwargs) = mock_tile_2.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_2_ID),
            BEAM_2_DELAY_AZIMUTH,
            BEAM_2_DELAY_RATE_AZIMUTH,
            BEAM_2_DELAY_ELEVATION,
            BEAM_2_DELAY_RATE_ELEVATION,
        ]
        mock_tile_3.SetPointingDelay.assert_not_called()
        mock_tile_4.SetPointingDelay.assert_not_called()

        ([result_code], _) = stationbeam_3.ApplyPointing()
        assert result_code == ResultCode.QUEUED

        mock_tile_1.SetPointingDelay.assert_not_called()
        mock_tile_2.SetPointingDelay.assert_not_called()

        (args, kwargs) = mock_tile_3.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_3_ID),
            BEAM_3_DELAY_AZIMUTH,
            BEAM_3_DELAY_RATE_AZIMUTH,
            BEAM_3_DELAY_ELEVATION,
            BEAM_3_DELAY_RATE_ELEVATION,
        ]
        (args, kwargs) = mock_tile_4.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_3_ID),
            BEAM_3_DELAY_AZIMUTH,
            BEAM_3_DELAY_RATE_AZIMUTH,
            BEAM_3_DELAY_ELEVATION,
            BEAM_3_DELAY_RATE_ELEVATION,
        ]

        ([result_code], _) = stationbeam_4.ApplyPointing()
        assert result_code == ResultCode.QUEUED

        mock_tile_1.SetPointingDelay.assert_not_called()
        mock_tile_2.SetPointingDelay.assert_not_called()
        (args, kwargs) = mock_tile_3.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_4_ID),
            BEAM_4_DELAY_AZIMUTH,
            BEAM_4_DELAY_RATE_AZIMUTH,
            BEAM_4_DELAY_ELEVATION,
            BEAM_4_DELAY_RATE_ELEVATION,
        ]
        (args, kwargs) = mock_tile_4.SetPointingDelay.get_next_call()
        assert not kwargs
        assert len(args) == 1
        assert list(args[0]) == [
            float(BEAM_4_ID),
            BEAM_4_DELAY_AZIMUTH,
            BEAM_4_DELAY_RATE_AZIMUTH,
            BEAM_4_DELAY_ELEVATION,
            BEAM_4_DELAY_RATE_ELEVATION,
        ]
