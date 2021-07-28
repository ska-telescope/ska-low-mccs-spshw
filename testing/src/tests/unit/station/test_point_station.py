########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""This module contains the tests for the ska_low_mccs.point_station module."""
from __future__ import annotations

import pytest

import numpy as np
from astropy.time.core import Time

from ska_low_mccs.station.point_station import (  # type:ignore[attr-defined]
    Pointing,
    StationInformation,
)

locationsfile = "testing/data/AAVS2_loc_italia_190429.txt"
outputfile = "testing/results/pointingtest.txt"
stat_lat, stat_lon, stat_height = (-26.82472208, 116.7644482, 346.59)


class TestPointStation:
    """Tests of point_station.py."""

    def test_create_pointing(self: TestPointStation) -> None:
        """Test pointing class instance and the supporting StationInformation object."""
        station = StationInformation()
        # Load standard AAVS displacements
        station.load_displacements(locationsfile)
        # Exercise bounds checks
        with pytest.raises(AssertionError):
            station.set_location(-111.11, stat_lon, stat_height)
            station.set_location(111.11, stat_lon, stat_height)
            station.set_location(stat_lat, -999.99, stat_height)
            station.set_location(stat_lat, 999.99, stat_height)
            station.set_location(stat_lat, stat_lon, -1234)
            station.set_location(stat_lat, stat_lon, 99999.99)
        # Set station reference position to array centre
        station.set_location(stat_lat, stat_lon, stat_height)
        # We have 256 elements and therefore expect a 256 x 3 array
        assert station.antennas.xyz.shape == (256, 3)
        # Check location data
        assert station.latitude == stat_lat
        assert station.longitude == stat_lon
        assert station.ellipsoidalheight == stat_height
        pointing = Pointing(station)

        point_kwargs = {
            "altitude": "90.0d",
            "azimuth": "0.0d",
        }
        pointing.point_array_static(**point_kwargs)
        # Pointing to zenith with flat station => zero delays
        assert np.mean(np.absolute(pointing._delays)) < 1e-15
        point_kwargs = {
            "altitude": "10.0d",
            "azimuth": "0.0d",
        }
        pointing.point_array_static(**point_kwargs)
        # Point near horizon => we get significant delays
        assert np.mean(np.absolute(pointing._delays)) > 1e-9

        # Exercise equatorial pointing near the SCP
        point_kwargs = {
            "pointing_time": Time("2021-05-09T23:00:00", format="isot", scale="utc"),
            "right_ascension": "0.0d",
            "declination": "-70.0d",
        }
        pointing.point_array(**point_kwargs)
        # Delays should be ns-scale
        assert np.mean(np.absolute(pointing._delays)) > 1e-9
        # Delay rates will be sub ps-scale
        assert np.mean(np.absolute(pointing._delay_rates)) > 1e-13
