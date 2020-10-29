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
    "path": "charts/ska-low-mccs/data/extra.json",
    "package": "ska.low.mccs",
    "device": "transientbuffer",
}


class TestMccsTransientBuffer(object):
    """
    Test class for MccsTransientBuffer tests.
    """

    def test_stationId(self, device_under_test):
        """
        Test for stationId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.stationId == ""

    def test_transientBufferJobId(self, device_under_test):
        """
        Test for transientBufferJobId

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.transientBufferJobId == ""

    def test_transientFrequencyWindow(self, device_under_test):
        """
        Test for transientFrequencyWindow

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.transientFrequencyWindow == (0.0,)

    def test_resamplingBits(self, device_under_test):
        """
        Test for resamplingBits

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.resamplingBits == 0

    def test_nStations(self, device_under_test):
        """
        Test for test_nStations

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.nStations == 0

    def test_stationIds(self, device_under_test):
        """
        Test for stationIds

        :param device_under_test: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :type device_under_test: :py:class:`tango.DeviceProxy`
        """
        assert device_under_test.stationIds == ("",)
