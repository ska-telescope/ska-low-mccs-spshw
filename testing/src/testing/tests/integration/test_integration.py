# type: ignore
"""This module contains integration tests of MCCS device interactions."""

import pytest
from time import sleep
from tango import DevState

from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsDeviceProxy
from ska_low_mccs.utils import call_with_json

from testing.harness.tango_harness import TangoHarness
from testing.harness import HelperClass


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
            {"name": "subarraybeam_01", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_02", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_03", "proxy": MccsDeviceProxy},
            {"name": "subarraybeam_04", "proxy": MccsDeviceProxy},
        ],
    }


class TestMccsIntegration(HelperClass):
    """Integration test cases for the Mccs device classes."""

    def check_states(self, dev_states):
        """
        Helper to check that each device is in the expected state with a timeout.

        :param dev_states: the devices and expected states of them
        :type dev_states: dict
        """
        for device, state in dev_states.items():
            count = 0.0
            while device.State() != state and count < 3.0:
                count += 0.1
                sleep(0.1)
            assert device.State() == state

    def test_controller_allocate_subarray(self, tango_harness: TangoHarness):
        """
        Test that an MccsController device can allocate resources to an MccsSubarray
        device.

        :param tango_harness: a test harness for tango devices
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subarray_1 = tango_harness.get_device("low-mccs/subarray/01")
        subarray_2 = tango_harness.get_device("low-mccs/subarray/02")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        tile_4 = tango_harness.get_device("low-mccs/tile/0004")

        # check initial state
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        controller.Startup()
        dev_states = {
            controller: DevState.ON,
            station_1: DevState.ON,
            station_2: DevState.ON,
            tile_1: DevState.ON,
            tile_2: DevState.ON,
            tile_3: DevState.ON,
            tile_4: DevState.ON,
        }
        self.check_states(dev_states)

        # allocate station_1 to subarray_1
        ((result_code,), (message, message_uid)) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert message
        self.wait_for_command_to_complete(controller)

        # check that station_1 and only station_1 is allocated
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating station_1 to subarray 2 should fail, because it is already
        # allocated to subarray 1
        ((result_code,), (message, message_uid)) = call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert message
        assert ":Allocate" in message_uid
        self.wait_for_command_to_complete(controller, expected_result=ResultCode.FAILED)

        # check no side-effects
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # allocating stations 1 and 2 to subarray 1 should succeed,
        # because the already allocated station is allocated to the same
        # subarray, BUT we must remember that the subarray cannot reallocate
        # the same subarray_beam.
        # ToDo This will change when subarray_beam is not a list.
        ((result_code,), (message, message_uid)) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1, 2]],
            subarray_beam_ids=[2],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert ":Allocate" in message_uid
        self.wait_for_command_to_complete(controller)

        # check
        assert list(subarray_1.stationFQDNs) == [
            station_1.dev_name(),
            station_2.dev_name(),
        ]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 1
        assert tile_4.subarrayId == 1

    def test_controller_release_subarray(self, tango_harness: TangoHarness):
        """
        Test that an MccsController device can release the resources of an MccsSubarray
        device.

        :param tango_harness: a test harness for tango devices
        """
        controller = tango_harness.get_device("low-mccs/control/control")
        subarray_1 = tango_harness.get_device("low-mccs/subarray/01")
        subarray_2 = tango_harness.get_device("low-mccs/subarray/02")
        station_1 = tango_harness.get_device("low-mccs/station/001")
        station_2 = tango_harness.get_device("low-mccs/station/002")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")
        tile_3 = tango_harness.get_device("low-mccs/tile/0003")
        tile_4 = tango_harness.get_device("low-mccs/tile/0004")

        controller.Startup()
        dev_states = {
            controller: DevState.ON,
            station_1: DevState.ON,
            station_2: DevState.ON,
            tile_1: DevState.ON,
            tile_2: DevState.ON,
            tile_3: DevState.ON,
            tile_4: DevState.ON,
        }
        self.check_states(dev_states)

        # allocate stations 1 to subarray 1
        ((result_code,), (message, message_uid)) = call_with_json(
            controller.Allocate,
            subarray_id=1,
            station_ids=[[1]],
            subarray_beam_ids=[1],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert ":Allocate" in message_uid
        self.wait_for_command_to_complete(controller)

        # allocate station 2 to subarray 2
        ((result_code,), (message, message_uid)) = call_with_json(
            controller.Allocate,
            subarray_id=2,
            station_ids=[[2]],
            subarray_beam_ids=[2],
            channel_blocks=[2],
        )
        assert result_code == ResultCode.QUEUED
        assert ":Allocate" in message_uid
        self.wait_for_command_to_complete(controller)

        # check initial state
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert list(subarray_2.stationFQDNs) == [station_2.dev_name()]
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 2
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 2
        assert tile_4.subarrayId == 2

        # release resources of subarray_2
        ((result_code,), (_,)) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.OK

        # check
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # releasing resources of unresourced subarray_2 should fail
        ((result_code,), (_,)) = call_with_json(
            controller.Release, subarray_id=2, release_all=True
        )
        assert result_code == ResultCode.FAILED

        # check no side-effect to failed release
        assert list(subarray_1.stationFQDNs) == [station_1.dev_name()]
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 1
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

        # release resources of subarray_1
        ((result_code,), (_,)) = call_with_json(
            controller.Release, subarray_id=1, release_all=True
        )
        assert result_code == ResultCode.OK

        # check all released
        assert subarray_1.stationFQDNs is None
        assert subarray_2.stationFQDNs is None
        assert station_1.subarrayId == 0
        assert station_2.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0
        assert tile_3.subarrayId == 0
        assert tile_4.subarrayId == 0

    def test_station_tile_subarray_id(self, tango_harness: TangoHarness):
        """
        Test that a write to attribute subarrayId on an MccsStation device also results
        in an update to attribute subarrayId on its MccsTiles.

        :param tango_harness: a test harness for tango devices
        """
        station = tango_harness.get_device("low-mccs/station/001")
        tile_1 = tango_harness.get_device("low-mccs/tile/0001")
        tile_2 = tango_harness.get_device("low-mccs/tile/0002")

        # check initial state
        assert station.subarrayId == 0
        assert tile_1.subarrayId == 0
        assert tile_2.subarrayId == 0

        # write subarray_id
        station.subarrayId = 1

        # check state
        assert station.subarrayId == 1
        assert tile_1.subarrayId == 1
        assert tile_2.subarrayId == 1
