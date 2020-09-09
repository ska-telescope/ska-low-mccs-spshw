#########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the MccsTransientBuffer project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
#########################################################################
"""
This module contains the tests for MccsTransientBuffer.
"""

device_to_load = {
    "path": "charts/mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "transientbuffer1",
}


class TestMccsTransientBuffer(object):
    """
    Test class for MccsTransientBuffer tests.
    """

    def test_stationId(self, device_under_test):
        """Test for stationId"""
        assert device_under_test.stationId == ""

    def test_transientBufferJobId(self, device_under_test):
        """Test for transientBufferJobId"""
        assert device_under_test.transientBufferJobId == ""

    def test_transientFrequencyWindow(self, device_under_test):
        """Test for transientFrequencyWindow"""
        assert device_under_test.transientFrequencyWindow == (0.0,)

    def test_resamplingBits(self, device_under_test):
        """Test for resamplingBits"""
        assert device_under_test.resamplingBits == 0

    def test_nStations(self, device_under_test):
        """Test for test_nStations"""
        assert device_under_test.nStations == 0

    def test_stationIds(self, device_under_test):
        """Test for stationIds"""
        assert device_under_test.stationIds == ("",)
