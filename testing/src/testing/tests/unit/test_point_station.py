########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska_low_mccs.health module.
"""

import pytest

# from tango import DevState
from tango import AttrQuality

from ska_tango_base.control_model import AdminMode, HealthState
from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.events import EventManager
from ska_low_mccs.health import (
    DeviceHealthPolicy,
    DeviceHealthRollupPolicy,
    DeviceHealthMonitor,
    HealthMonitor,
    HealthModel,
    MutableHealthMonitor,
    MutableHealthModel,
)


# from testing.harness.mock import MockDeviceBuilder
# from testing.harness.tango_harness import TangoHarness

from ska_low_mccs import point_station

locationsfile = "testing/data/AAVS2_loc_italia_190429.txt"
stat_lat, stat_lon, stat_height = (-26.82472208, 116.7644482, 346.59)

# @pytest.fixture()
# def mock_factory(mocker):
#     """
#     Fixture that provides a mock factory for device proxy mocks. This
#     default factory provides vanilla mocks, but this fixture can be
#     overridden by test modules/classes to provide mocks with specified
#     behaviours.

#     :param mocker: the pytest `mocker` fixture is a wrapper around the
#         `unittest.mock` package
#     :type mocker: :py:class:`pytest_mock.mocker`

#     :return: a factory for device proxy mocks
#     :rtype: :py:class:`unittest.mock.Mock` (the class itself, not an
#         instance)
#     """
#     builder = MockDeviceBuilder()
#     builder.add_attribute("healthState", HealthState.UNKNOWN)
#     builder.add_attribute("adminMode", AdminMode.ONLINE)
#     return builder


class TestPointStation:
    """
    ASDF.
    """

    def test_create_pointing(self):
        station = point_station.StationInformation()
        station.loaddisplacements(locationsfile)
        station.setlocation(stat_lat, stat_lon, stat_height)
        assert station.latitude == stat_lat
        assert station.longitude == stat_lon
        assert station.ellipsoidalheight == stat_height
        pointing = point_station.Pointing(station)
        print(pointing)

        # assert(retval == 1)
