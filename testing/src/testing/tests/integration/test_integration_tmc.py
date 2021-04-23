"""
This module contains tests of interactions between the TMC and
ska_low_mccs classes.
"""
import json

import pytest
from tango import (
    DevState,
    AsynCall,
    AsynReplyNotArrived,
    CommunicationFailed,
    DevFailed,
)

from ska_tango_base.commands import ResultCode
from ska_tango_base.control_model import ObsState

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


class TestMccsIntegrationTmc:
    """
    Integration test cases for interactions between TMC and MCCS device
    classes.
    """

    @pytest.fixture()
    def devices(self, tango_harness: TangoHarness):
        """
        Fixture that provides access to devices via their names.

        :todo: For now the purpose of this fixture is to isolate FQDNs
            in a single place in this module. In future this will be
            changed to extract the device FQDNs straight from the
            configuration file.

        :param tango_harness: a test harness for tango devices

        :return: a dictionary of devices keyed by their name
        :rtype: dict<string, :py:class:`tango.DeviceProxy`>
        """
        device_dict = {
            "controller": tango_harness.get_device("low-mccs/control/control"),
            "subarray_01": tango_harness.get_device("low-mccs/subarray/01"),
            "subarray_02": tango_harness.get_device("low-mccs/subarray/02"),
            "station_001": tango_harness.get_device("low-mccs/station/001"),
            "station_002": tango_harness.get_device("low-mccs/station/002"),
            "tile_0001": tango_harness.get_device("low-mccs/tile/0001"),
            "tile_0002": tango_harness.get_device("low-mccs/tile/0002"),
            "tile_0003": tango_harness.get_device("low-mccs/tile/0003"),
            "tile_0004": tango_harness.get_device("low-mccs/tile/0004"),
            # workaround for https://github.com/tango-controls/cppTango/issues/816
            # "antenna_000001": tango_harness.get_device("low-mccs/antenna/000001"),
            # "antenna_000002": tango_harness.get_device("low-mccs/antenna/000002"),
            # "antenna_000003": tango_harness.get_device("low-mccs/antenna/000003"),
            # "antenna_000004": tango_harness.get_device("low-mccs/antenna/000004"),
            "subarraybeam_01": tango_harness.get_device("low-mccs/subarraybeam/01"),
            "subarraybeam_02": tango_harness.get_device("low-mccs/subarraybeam/02"),
            "subarraybeam_03": tango_harness.get_device("low-mccs/subarraybeam/03"),
            "subarraybeam_04": tango_harness.get_device("low-mccs/subarraybeam/04"),
        }
        return device_dict

    def assert_command(
        self, device, command, argin=None, expected_result=ResultCode.OK
    ):
        """
        Method to simplify assertions on the result of TMC calls.

        :param device: The MCCS device to send command to
        :type device: :py:class:`tango.DeviceProxy`
        :param command: The command to send to the device
        :type command: str
        :param argin: Optional argument to send to the command
        :type argin: str
        :param expected_result: The expected return code from the command
        :type expected_result: :py:class:`~ska_tango_base.commands.ResultCode`
        """
        # Call the specified command asynchronously
        async_id = device.command_inout_asynch(command, argin)
        try:
            # HACK: increasing the timeout until we can make some commands synchronous
            result = device.command_inout_reply(async_id, timeout=0)
            if expected_result is None:
                assert result is None
            else:
                ((result_code,), (_,)) = result
                assert result_code == expected_result
        except AsynReplyNotArrived as err:
            assert False, f"AsyncReplyNotArrived: {err}"
        except (AsynCall, CommunicationFailed, DevFailed) as err:
            assert False, f"Exception raised: {err}"

    def test_controller_on(self, devices):
        """
        Test that an asynchronous call to controller:On() works
        correctly.

        :param devices: fixture that provides access to devices by their name
        :type devices: dict<string, :py:class:`tango.DeviceProxy`>
        """
        assert devices["controller"].State() == DevState.DISABLE
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF

        # Call MccsController->Startup() command
        self.assert_command(device=devices["controller"], command="Startup")
        assert devices["controller"].State() == DevState.ON
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.ON
        assert devices["station_002"].State() == DevState.ON

        # Startup turns everything on, so a call to On should have no side-effects
        self.assert_command(device=devices["controller"], command="On")
        assert devices["controller"].State() == DevState.ON
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.ON
        assert devices["station_002"].State() == DevState.ON

    def test_controller_off(self, devices):
        """
        Test that an asynchronous call to controller:Off() works
        correctly.

        :param devices: fixture that provides access to devices by their name
        :type devices: dict<string, :py:class:`tango.DeviceProxy`>
        """
        assert devices["controller"].State() == DevState.DISABLE
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF
        self.assert_command(device=devices["controller"], command="Startup")
        assert devices["controller"].State() == DevState.ON
        assert devices["station_001"].State() == DevState.ON
        assert devices["station_002"].State() == DevState.ON
        self.assert_command(device=devices["controller"], command="Off")
        assert devices["controller"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF

    def test_setup_only(self, devices):
        """
        Test that runs through the basic TMC<->MCCS interactions to
        setup and then tear down.

        :param devices: fixture that provides access to devices by their name
        :type devices: dict<string, :py:class:`tango.DeviceProxy`>
        """
        # Turn on controller and stations
        self.assert_command(device=devices["controller"], command="Startup")
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0
        assert list(devices["subarray_01"].stationFQDNs) == []

        # Allocate stations to a subarray
        parameters = {
            "subarray_id": 1,
            "station_ids": [1, 2],
            "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
            "subarray_beam_ids": [1],
        }
        devices["subarraybeam_01"].isBeamLocked = True
        json_string = json.dumps(parameters)
        self.assert_command(
            device=devices["controller"], command="Allocate", argin=json_string
        )
        assert devices["station_001"].subarrayId == 1
        assert devices["station_002"].subarrayId == 1
        assert devices["subarray_01"].State() == DevState.ON
        assert devices["subarray_01"].obsState == ObsState.IDLE
        assert sorted(devices["subarray_01"].stationFQDNs) == [
            "low-mccs/station/001",
            "low-mccs/station/002",
        ]

        # Release Resources
        release_config = {"subarray_id": 1, "release_all": True}
        json_string = json.dumps(release_config)
        self.assert_command(
            device=devices["controller"], command="Release", argin=json_string
        )
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["subarray_01"].State() == DevState.OFF
        assert list(devices["subarray_01"].stationFQDNs) == []
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Turn off controller and stations
        self.assert_command(device=devices["controller"], command="Off")
        assert devices["controller"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF

    def test_setup_and_observation(self, devices):
        """
        Test that runs through the basic TMC<->MCCS interactions to
        setup and perform an observation (without pointing updates)

        :param devices: fixture that provides access to devices by their name
        :type devices: dict<string, :py:class:`tango.DeviceProxy`>
        """
        # Turn on controller and stations
        self.assert_command(device=devices["controller"], command="Startup")
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Allocate stations to a subarray
        parameters = {
            "subarray_id": 1,
            "station_ids": [1, 2],
            "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
            "subarray_beam_ids": [1],
        }
        json_string = json.dumps(parameters)
        self.assert_command(
            device=devices["controller"], command="Allocate", argin=json_string
        )
        assert devices["station_001"].subarrayId == 1
        assert devices["station_002"].subarrayId == 1
        assert devices["subarray_01"].State() == DevState.ON
        assert devices["subarray_01"].obsState == ObsState.IDLE

        # Configure the subarray
        configuration = {
            "stations": [{"station_id": 1}, {"station_id": 2}],
            "subarray_beams": [
                {
                    "subarray_id": 1,
                    "subarray_beam_id": 1,
                    "station_ids": [1, 2],
                    "channels": [[0, 8, 1, 1], [8, 8, 2, 1]],
                    "update_rate": 0.0,
                    "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                }
            ],
        }
        json_string = json.dumps(configuration)
        self.assert_command(
            device=devices["subarray_01"], command="Configure", argin=json_string
        )
        assert devices["subarray_01"].obsState == ObsState.READY

        # Perform a scan on the subarray
        scan_config = {"id": 1, "scan_time": 4}
        json_string = json.dumps(scan_config)
        self.assert_command(
            device=devices["subarray_01"],
            command="Scan",
            argin=json_string,
            expected_result=ResultCode.STARTED,
        )
        assert devices["subarray_01"].obsState == ObsState.SCANNING

        # End a scan
        self.assert_command(device=devices["subarray_01"], command="EndScan")
        assert devices["subarray_01"].obsState == ObsState.READY

        # Prepare for and release Resources
        self.assert_command(device=devices["subarray_01"], command="End")
        assert devices["subarray_01"].obsState == ObsState.IDLE
        release_config = {"subarray_id": 1, "release_all": True}
        json_string = json.dumps(release_config)
        self.assert_command(
            device=devices["controller"], command="Release", argin=json_string
        )
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["subarray_01"].State() == DevState.OFF
        assert list(devices["subarray_01"].stationFQDNs) == []
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Turn off controller and stations
        self.assert_command(device=devices["controller"], command="Off")
        assert devices["controller"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF
