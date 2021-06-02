# type: ignore
"""This module contains tests of interactions between ska_low_mccs classes, particularly
tango devices."""

import pytest

from ska_low_mccs import MccsDeviceProxy

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
        "path": "charts/ska-low-mccs/data/configuration.json",
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
    """Integration test cases for the Mccs device classes."""

    def test_stationbeam_apply_pointing(self, tango_harness: TangoHarness):
        """
        Test that a MccsStationBeam device can apply delays to associated MccsTile
        devices.

        :param tango_harness: a test harness for tango devices
        """
        stationbeam_1 = tango_harness.get_device("low-mccs/beam/001")
        stationbeam_2 = tango_harness.get_device("low-mccs/beam/002")
        stationbeam_3 = tango_harness.get_device("low-mccs/beam/003")
        stationbeam_4 = tango_harness.get_device("low-mccs/beam/004")

        stationbeam_1.pointingDelay = [1.0e-9] * 2
        stationbeam_2.pointingDelay = [2.0e-9] * 2
        stationbeam_3.pointingDelay = [3.0e-9] * 2
        stationbeam_4.pointingDelay = [4.0e-9] * 2
        stationbeam_1.pointingDelayRate = [0.1e-11] * 2
        stationbeam_2.pointingDelayRate = [0.2e-11] * 2
        stationbeam_3.pointingDelayRate = [0.3e-11] * 2
        stationbeam_4.pointingDelayRate = [0.4e-11] * 2

        # allocate does not currently include station_beams, so assigning manually
        stationbeam_1.stationFqdn = "low-mccs/station/001"
        stationbeam_1.logicalBeamId = 1
        stationbeam_2.stationFqdn = "low-mccs/station/001"
        stationbeam_2.logicalBeamId = 2
        stationbeam_3.stationFqdn = "low-mccs/station/002"
        stationbeam_3.logicalBeamId = 3
        stationbeam_4.stationFqdn = "low-mccs/station/002"
        stationbeam_4.logicalBeamId = 4

        # set_pointing_delay not currently implemented in base_tpm_simulator
        # so check the error is returned on stationbeam.ApplyPointing()
        with pytest.raises(Exception) as notimplementederror:
            assert stationbeam_1.ApplyPointing()
        assert "NotImplementedError" in str(notimplementederror.value)
        with pytest.raises(Exception) as notimplementederror:
            assert stationbeam_2.ApplyPointing()
        assert "NotImplementedError" in str(notimplementederror.value)
        with pytest.raises(Exception) as notimplementederror:
            assert stationbeam_3.ApplyPointing()
        assert "NotImplementedError" in str(notimplementederror.value)
        with pytest.raises(Exception) as notimplementederror:
            assert stationbeam_4.ApplyPointing()
        assert "NotImplementedError" in str(notimplementederror.value)
