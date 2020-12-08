"""
This module contains tests of interactions between the TMC and
ska.low.mccs classes.
"""
import json

import pytest
from tango import (
    DevState,
    DevSource,
    AsynCall,
    AsynReplyNotArrived,
    CommunicationFailed,
    DevFailed,
)

from ska.base.commands import ResultCode
from ska.base.control_model import ObsState

from conftest import confirm_initialised


@pytest.fixture()
def devices_to_load():
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    :rtype: dict
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska.low.mccs",
        "devices": [
            "controller",
            "subarray_01",
            "subarray_02",
            "station_001",
            "station_002",
            "tile_0001",
            "tile_0002",
            "tile_0003",
            "tile_0004",
            "apiu_001",
            # "antenna_000001",  # workaround for MCCS-244
            # "antenna_000002",
            # "antenna_000003",
            # "antenna_000004",
        ],
    }


class TestMccsIntegrationTmc:
    """
    Integration test cases for interactions between TMC and Mccs device
    classes.
    """

    @pytest.fixture()
    def devices(self, device_context):
        """
        Fixture that provides access to devices via their names.

        :todo: For now the purpose of this fixture is to isolate FQDNs in a
            single place in this module. In future this will be changed to
            extract the device FQDNs straight from the configuration file.

        :param device_context: fixture that provides a tango context of some
            sort
        :type device_context: a tango context of some sort; possibly a
            MultiDeviceTestContext, possibly the real thing. The only
            requirement is that it provide a "get_device(fqdn)" method that
            returns a DeviceProxy.

        :return: a dictionary of devices keyed by their name
        :rtype: dict<string, :py:class:`tango.DeviceProxy`>
        """
        device_dict = {
            "controller": device_context.get_device("controller"),
            "subarray_01": device_context.get_device("subarray_01"),
            "subarray_02": device_context.get_device("subarray_02"),
            "station_001": device_context.get_device("station_001"),
            "station_002": device_context.get_device("station_002"),
            "tile_0001": device_context.get_device("tile_0001"),
            "tile_0002": device_context.get_device("tile_0002"),
            "tile_0003": device_context.get_device("tile_0003"),
            "tile_0004": device_context.get_device("tile_0004"),
            # workaround for MCCS-244
            # "antenna_000001": device_context.get_device("antenna_000001"),
            # "antenna_000002": device_context.get_device("antenna_000002"),
            # "antenna_000003": device_context.get_device("antenna_000003"),
            # "antenna_000004": device_context.get_device("antenna_000004"),
        }
        confirm_initialised(device_dict.values())
        return device_dict

    def set_all_dev_source(self, devices):
        """
        Set all of the devices to DevSource.DEV source.

        :param devices: fixture that provides access to devices by their name
        :type devices: dict<string, :py:class:`tango.DeviceProxy`>
        """
        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period to test that the write has stuck.
        for device in devices.values():
            device.set_source(DevSource.DEV)

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
        :type expected_result: :py:class:`~ska.base.commands.ResultCode`
        """
        # Call the specified command asynchronously
        async_id = device.command_inout_asynch(command, argin)
        try:
            result = device.command_inout_reply(async_id, timeout=5000)
            if expected_result is None:
                assert result is None
            else:
                assert result[0] == expected_result
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
        self.set_all_dev_source(devices)

        assert devices["controller"].State() == DevState.OFF
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF

        # Call MccsController->On() command
        self.assert_command(device=devices["controller"], command="On")
        assert devices["controller"].State() == DevState.ON
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_02"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.ON
        assert devices["station_002"].State() == DevState.ON

        # A second call to On should have no side-effects
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
        self.set_all_dev_source(devices)

        assert devices["controller"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF
        self.assert_command(device=devices["controller"], command="On")
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
        self.set_all_dev_source(devices)

        # Turn on controller and stations
        self.assert_command(device=devices["controller"], command="On")
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Allocate stations to a subarray
        parameters = {
            "subarray_id": 1,
            "station_ids": [1, 2],
            "channels": [1, 2, 3, 4, 5, 6, 7, 8],
            "station_beam_ids": [1],
        }
        json_string = json.dumps(parameters)
        self.assert_command(
            device=devices["controller"], command="Allocate", argin=json_string
        )
        assert devices["station_001"].subarrayId == 1
        assert devices["station_002"].subarrayId == 1
        assert devices["subarray_01"].State() == DevState.ON
        assert devices["subarray_01"].obsState == ObsState.IDLE

        # Release Resources
        release_config = {"subarray_id": 1, "release_all": True}
        json_string = json.dumps(release_config)
        self.assert_command(
            device=devices["controller"], command="Release", argin=json_string
        )
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_01"].stationFQDNs is None
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
        self.set_all_dev_source(devices)

        # Turn on controller and stations
        self.assert_command(device=devices["controller"], command="On")
        assert devices["subarray_01"].State() == DevState.OFF
        assert devices["subarray_01"].obsState == ObsState.EMPTY
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Allocate stations to a subarray
        parameters = {
            "subarray_id": 1,
            "station_ids": [1, 2],
            "channels": [1, 2, 3, 4, 5, 6, 7, 8],
            "station_beam_ids": [1],
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
            "station_beam_pointings": [
                {
                    "station_beam_id": 1,  # should correspond to one in the
                    # station_beam_ids in the resources
                    "target": {
                        "system": "HORIZON",  # Target coordinate system
                        "name": "DriftScan",  # Source name - metadata only,
                        # does not need to be resolved
                        "Az": 180.0,  # This is in degrees
                        "El": 45.0,  # Ditto
                    },
                    "update_rate": 0.0,  # seconds - never update for a drift scan
                    # should be a subset of the channels in the resources
                    "channels": [1, 2, 3, 4, 5, 6, 7, 8],
                }
            ],
        }
        json_string = json.dumps(configuration)
        self.assert_command(
            device=devices["subarray_01"], command="Configure", argin=json_string
        )
        assert devices["subarray_01"].obsState == ObsState.READY

        # Perform a scan on the subarray
        scan_config = {"id": 1}
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
        assert devices["subarray_01"].stationFQDNs is None
        assert devices["station_001"].subarrayId == 0
        assert devices["station_002"].subarrayId == 0

        # Turn off controller and stations
        self.assert_command(device=devices["controller"], command="Off")
        assert devices["controller"].State() == DevState.OFF
        assert devices["station_001"].State() == DevState.OFF
        assert devices["station_002"].State() == DevState.OFF
