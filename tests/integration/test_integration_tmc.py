"""
This module contains tests of interactions between the TMC and ska.low.mccs classes.
"""
from concurrent.futures import Future
from tango import DevState, DevSource
from ska.base.commands import ResultCode
from ska.base.control_model import ObsState
import tango
import json

devices_to_load = {
    "path": "charts/mccs/data/configuration.json",
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
        "antenna_000001",
        "antenna_000002",
        "antenna_000003",
        "antenna_000004",
    ],
}


class TestMccsIntegrationTmc:
    """
    Integration test cases for interactions between TMC and Mccs device classes
    """

    def async_init(self):
        """
        Method that initialises the Tango instance to enable callback functions
        """
        api_util = tango.ApiUtil.instance()
        api_util.set_asynch_cb_sub_model(tango.cb_sub_model.PUSH_CALLBACK)

    def async_command(self, device, command, argin=None, expected_result=ResultCode.OK):
        """
        Method to simplfy the TMC calls for asynchronous commands

        :param device: The MCCS device to send command to
        :type device: :py:class:`tango.DeviceProxy`
        :param command: The command to send to the device
        :type command: str
        :param argin: Optional argument to send to the command
        :type argin: str
        :param expected_result: The expected return code from the command
        :type expected_result: :py:class:`ska.base.commands.ResultCode`
        """
        future = Future()
        # Call the specified command asynchronously
        if argin is None:
            device.command_inout_asynch(command, future.set_result)
        else:
            device.command_inout_asynch(command, argin, future.set_result)
        result = future.result(timeout=0.5)
        if expected_result is None:
            assert result.argout is None
        else:
            assert result.argout[0] == expected_result

    def test_controller_on(self, device_context):
        """
        Test that an asynchronous call to controller:On() works correctly

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        self.async_init()
        controller = device_context.get_device("low-mccs/control/control")
        station001 = device_context.get_device("low-mccs/station/001")
        station002 = device_context.get_device("low-mccs/station/002")
        subarray01 = device_context.get_device("low-mccs/subarray/01")
        subarray02 = device_context.get_device("low-mccs/subarray/02")
        assert controller.State() == DevState.OFF
        assert subarray01.State() == DevState.OFF
        assert subarray02.State() == DevState.OFF
        assert station001.State() == DevState.OFF
        assert station002.State() == DevState.OFF

        # Call MccsController->On() command
        self.async_command(device=controller, command="On")
        assert controller.State() == DevState.ON
        assert subarray01.State() == DevState.OFF
        assert subarray02.State() == DevState.OFF
        # TODO: The stations are in alarm state because MCCS-212
        assert station001.State() == DevState.ALARM
        assert station002.State() == DevState.ALARM

        # # A second call to On should have no side-effects
        # self.async_command(device=controller, command="On", expected_result=None)
        # assert controller.State() == DevState.ON
        # assert subarray01.State() == DevState.OFF
        # assert subarray02.State() == DevState.OFF
        # # TODO: The stations are in alarm state because MCCS-212
        # assert station001.State() == DevState.ALARM
        # assert station002.State() == DevState.ALARM

    def test_controller_off(self, device_context):
        """
        Test that an asynchronous call to controller:Off() works correctly

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        self.async_init()
        controller = device_context.get_device("low-mccs/control/control")
        station001 = device_context.get_device("low-mccs/station/001")
        station002 = device_context.get_device("low-mccs/station/002")
        assert controller.State() == DevState.OFF
        assert station001.State() == DevState.OFF
        assert station002.State() == DevState.OFF
        self.async_command(device=controller, command="On")
        assert controller.State() == DevState.ON
        # TODO: The stations are in alarm state because MCCS-212
        assert station001.State() == DevState.ALARM
        assert station002.State() == DevState.ALARM
        self.async_command(device=controller, command="Off")
        assert controller.State() == DevState.OFF
        assert station001.State() == DevState.OFF
        assert station002.State() == DevState.OFF

    def test_setup_and_observation(self, device_context):
        """
        Test that runs through the basic TMC<->MCCS interactions to setup and
        perform an observation (without pointing updates)

        :param device_context: a test context for a set of tango devices
        :type device_context: :py:class:`tango.MultiDeviceTestContext`
        """
        self.async_init()
        controller = device_context.get_device("low-mccs/control/control")
        subarray = device_context.get_device("low-mccs/subarray/01")
        station_001 = device_context.get_device("low-mccs/station/001")
        station_002 = device_context.get_device("low-mccs/station/002")

        # Bypass the cache because stationFQDNs etc are polled attributes,
        # and having written to them, we don't want to have to wait a
        # polling period to test that the write has stuck.
        controller.set_source(DevSource.DEV)
        subarray.set_source(DevSource.DEV)
        station_001.set_source(DevSource.DEV)
        station_002.set_source(DevSource.DEV)

        # Turn on controller and stations
        self.async_command(device=controller, command="On")
        parameters = {
            "subarray_id": 1,
            "station_ids": [1, 2],
            "channels": [1, 2, 3, 4, 5, 6, 7, 8],
            "station_beam_ids": [1],
        }
        json_string = json.dumps(parameters)
        assert subarray.State() == DevState.OFF
        assert subarray.obsState == ObsState.EMPTY
        assert station_001.subarrayId == 0
        assert station_002.subarrayId == 0

        # Allocate stations to a subarray
        self.async_command(device=controller, command="Allocate", argin=json_string)
        assert station_001.subarrayId == 1
        assert station_002.subarrayId == 1
        assert subarray.State() == DevState.ON
        assert subarray.obsState == ObsState.IDLE

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
                    "channels": [
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        7,
                        8,
                    ],  # should be a subset of the channels in the resources
                }
            ],
        }
        json_string = json.dumps(configuration)
        self.async_command(device=subarray, command="Configure", argin=json_string)
        assert subarray.obsState == ObsState.READY

        # Perform a scan on the subarray
        scan_config = {"id": 1}
        json_string = json.dumps(scan_config)
        self.async_command(
            device=subarray,
            command="Scan",
            argin=json_string,
            expected_result=ResultCode.STARTED,
        )
        assert subarray.obsState == ObsState.SCANNING

        # End a scan
        self.async_command(device=subarray, command="EndScan")
        assert subarray.obsState == ObsState.READY

        # Prepare for and release Resources
        self.async_command(device=subarray, command="End")
        assert subarray.obsState == ObsState.IDLE
        release_config = {"subarray_id": 1, "release_all": True}
        json_string = json.dumps(release_config)
        self.async_command(device=controller, command="Release", argin=json_string)
        assert subarray.obsState == ObsState.EMPTY
        assert subarray.State() == DevState.OFF
