"""
This module contains tests of interactions between ska_low_mccs classes,
particularly tango devices.
"""

import pytest

from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.utils import call_with_json

from testing.harness.tango_harness import TangoHarness


@pytest.fixture()
def devices_to_load():
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    :rtype: dict
    """
    # TODO: Once https://github.com/tango-controls/cppTango/issues/816 is resolved, we
    # should reinstate the APIUs and antennas in these tests.
    return {
        "path": "charts/ska-low-mccs/data/configuration_without_antennas.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "controller", "proxy": MccsDeviceProxy},
            {"name": "subarray_01", "proxy": MccsDeviceProxy},
            {"name": "subarray_02", "proxy": MccsDeviceProxy},
            {"name": "station_001", "proxy": MccsDeviceProxy},
            {"name": "station_002", "proxy": MccsDeviceProxy},
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            {"name": "tile_0002", "proxy": MccsDeviceProxy},
            {"name": "tile_0003", "proxy": MccsDeviceProxy},
            {"name": "tile_0004", "proxy": MccsDeviceProxy},
            {"name": "beam_001", "proxy": MccsDeviceProxy},
            {"name": "beam_002", "proxy": MccsDeviceProxy},
            {"name": "beam_003", "proxy": MccsDeviceProxy},
            {"name": "beam_004", "proxy": MccsDeviceProxy},
        ],
    }


class TestMccsIntegration:
    """
    Integration test cases for the Mccs device classes.
    """

    def test_stationbeam_apply_pointing(self, tango_harness: TangoHarness):
        """
        Test that an MccsController device can allocate resources to an
        MccsSubarray device.

        :param tango_harness: a test harness for tango devices
        """

        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        tile_4 = tango_harness.get_device("low-mccs/tile/0004")
        stationbeam_1 = tango_harness.get_device("low-mccs/beam/001")
        stationbeam_2 = tango_harness.get_device("low-mccs/beam/002")
        stationbeam_3 = tango_harness.get_device("low-mccs/beam/003")
        stationbeam_4 = tango_harness.get_device("low-mccs/beam/004")

        stationbeam_1._pointing_delay = [1.0] * 512
        stationbeam_2._pointing_delay = [2.0] * 512
        stationbeam_3._pointing_delay = [3.0] * 512
        stationbeam_4._pointing_delay = [4.0] * 512

        # allocate does not currently include station_beams, so assigning manually
        stationbeam_1._station_fqdn = "low-mccs/station/001"
        stationbeam_1.logicalBeamId = 1
        stationbeam_2._station_fqdn = "low-mccs/station/001"
        stationbeam_2.logicalBeamId = 2
        stationbeam_3._station_fqdn = "low-mccs/station/002"
        stationbeam_3.logicalBeamId = 3
        stationbeam_4._station_fqdn = "low-mccs/station/002"
        stationbeam_4.logicalBeamId = 4

        stationbeam_1.ApplyPointing()
        tile_1.assert_called_with([1] + [1.0] * 512)
        tile_2.assert_called_with([2] + [2.0] * 512)
        tile_3.assert_called_with([3] + [3.0] * 512)
        tile_4.assert_called_with([4] + [4.0] * 512)
