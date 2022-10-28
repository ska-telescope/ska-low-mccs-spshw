# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import pytest
from ska_low_mccs import tile
from ska_low_mccs.subrack import subrack_device
import time
import tango
from ska_control_model import AdminMode, PowerState, ResultCode, TaskStatus
from ska_low_mccs_common import MccsDeviceProxy
from ska_low_mccs_common.testing.mock import MockChangeEventCallback, MockCallable
from ska_low_mccs_common.testing.tango_harness import DevicesToLoadType, TangoHarness


@pytest.fixture()
def devices_to_load() -> DevicesToLoadType:
    """
    Fixture that specifies the devices to be loaded for testing.

    :return: specification of the devices to be loaded
    """
    return {
        "path": "charts/ska-low-mccs/data/configuration.json",
        "package": "ska_low_mccs",
        "devices": [
            {"name": "subrack_01", "proxy": MccsDeviceProxy},
            {"name": "tile_0001", "proxy": MccsDeviceProxy},
            #{"name": "daq_01", "proxy": MccsDeviceProxy}, - this will be needed when daq gets its first release
        ],
    }

class TestSubrackTileDaqIntegration:
    """Integration test cases for interactions between subrack and tile."""


    #@pytest.mark.xfail
    @pytest.mark.timeout(10)
    def test_subrack_tile_daq_integration(
        self: TestSubrackTileDaqIntegration,
        tango_harness: TangoHarness,
        subrack_device_admin_mode_changed_callback: MockChangeEventCallback,
        subrack_device_state_changed_callback: MockChangeEventCallback,
        tile_device_admin_mode_changed_callback: MockChangeEventCallback,
        lrc_result_changed_callback: MockChangeEventCallback,
        tile_device_state_changed_callback: MockChangeEventCallback,
        daq_device_state_changed_callback: MockChangeEventCallback
    ) -> None:
        """
        Summary of test

        :param self: _description_
        :param tango_harness: _description_
        :param subrack_device_admin_mode_changed_callback: _description_
        :param subrack_device_state_changed_callback: _description_
        :param tile_device_admin_mode_changed_callback: _description_
        :param lrc_result_changed_callback: _description_
        :param tile_device_state_changed_callback: _description_
        
        Turn on subrack
        Turn on tpm
        Turn on DAQ
        TPM should tell the subrack to turn tile on
        Subrack returns a ChangeAtrributeEvent
        TPM then initialises
        Verify that TPM has initialised, returning a tileProgrammingState
        Call StartAcquisition on TPM
        Verify that TPM has syncnhronised, returning a tileProgrammingState
        Call configure on the DAQ
        Call SendData on the TPM which sends a SPEAD packet to the DAQ
        """
        
        tile_device = tango_harness.get_device("low-mccs/tile/0001")
        subrack_device = tango_harness.get_device("low-mccs/subrack/01")
        #TODO: Make daq_device a daq tango device rather than None
        daq_device: MccsDeviceProxy = None 
        tpm_id = 1
        processed_data_callback = MockCallable()
        
        def configure_and_verify_callbacks():
            
            tile_device.add_change_event_callback(
                "adminMode",
                tile_device_admin_mode_changed_callback,
            )
            tile_device_admin_mode_changed_callback.assert_next_change_event(
                AdminMode.OFFLINE
            )

            tile_device.add_change_event_callback(
                "state",
                tile_device_state_changed_callback,
            )
            tile_device_state_changed_callback.assert_next_change_event(
                tango.DevState.DISABLE
            )

            subrack_device.add_change_event_callback(
                "adminMode",
                subrack_device_admin_mode_changed_callback,
            )
            subrack_device_admin_mode_changed_callback.assert_next_change_event(
                AdminMode.OFFLINE
            )

            subrack_device.add_change_event_callback(
                "state",
                subrack_device_state_changed_callback,
            )
            subrack_device_state_changed_callback.assert_last_change_event(
                tango.DevState.DISABLE
            )

            assert subrack_device.tpm1PowerState == PowerState.UNKNOWN

            # Subscribe to subrack's LRC result attribute
            subrack_device.add_change_event_callback(
                "longRunningCommandResult",
                lrc_result_changed_callback,
            )
            assert (
                "longRunningCommandResult".casefold()
                in subrack_device._change_event_subscription_ids
            )
            initial_lrc_result = ("", "")
            assert subrack_device.longRunningCommandResult == initial_lrc_result
            lrc_result_changed_callback.assert_next_change_event(initial_lrc_result)

            tile_device.adminMode = AdminMode.ONLINE

            tile_device_admin_mode_changed_callback.assert_last_change_event(
                AdminMode.ONLINE
            )
            # Before the tile device tries to connect with its TPM, it need to find out from
            # its subrack whether the TPM is event turned on. So it subscribes to change
            # events on the state of its subrack Tango device. The subrack device advises it
            # that it is OFFLINE. Therefore tile remains in UNKNOWN state.
            tile_device_state_changed_callback.assert_next_change_event(
                tango.DevState.UNKNOWN
            )
            assert tile_device.state() == tango.DevState.UNKNOWN

            subrack_device.adminMode = AdminMode.ONLINE
            subrack_device_admin_mode_changed_callback.assert_last_change_event(
                AdminMode.ONLINE
            )
        
        def turn_on_subrack():
            # The subrack device tries to establish a connection to its upstream power
            # supply device. Until this connection is established, it is in UNKNOWN state.
            subrack_device_state_changed_callback.assert_next_change_event(
                tango.DevState.UNKNOWN
            )

            # The subrack device connects to its upstream power supply device and finds that
            # the subrack is turned off, so it transitions to OFF state
            subrack_device_state_changed_callback.assert_last_change_event(
                tango.DevState.OFF
            )
            assert subrack_device.tpm1PowerState == PowerState.NO_SUPPLY

            # The tile device receives a change event. Since the event indicates that the
            # subrack hardware is OFF, the tile has established that its TPM is not powered,
            # so it transitions to OFF state.
            tile_device_state_changed_callback.assert_next_change_event(tango.DevState.OFF)
            assert tile_device.state() == tango.DevState.OFF

            [result_code], [unique_id] = subrack_device.On()
            # The subrack device tells the upstream power supply to power the subrack on.
            # Once the upstream power supply has powered the subrack on, the subrack device
            # tries to establish a connection to the subrack. Until that connection is
            # established, it is in UNKNOWN state.

            # TODO: Subrack is going straight to ON and not transitioning through UNKNOWN
            # subrack_device_state_changed_callback.assert_next_change_event(
            #     tango.DevState.UNKNOWN
            # )

            # Once the subrack device is connected to its subrack, it transitions to ON
            # state.
            subrack_device_state_changed_callback.assert_last_change_event(
                tango.DevState.ON
            )
            assert subrack_device.tpm1PowerState == PowerState.OFF

            lrc_result_changed_callback.assert_next_call(
                "longrunningcommandresult",
                (unique_id, '"On command has completed"'),
                tango.AttrQuality.ATTR_VALID,
            )

            # The tile device is notified that its subrack is on. It now has communication
            # with its TPM. The first thing it does is subscribe to change events on the
            # power mode of its TPM. It is informed that the TPM is turned off, so it
            # remains in OFF state
            tile_device_state_changed_callback.assert_not_called()
            assert tile_device.state() == tango.DevState.OFF

        def turn_on_tpm():
            
            [result_code], [unique_id] = tile_device.On()

            # The tile device tells the subrack device to tell its subrack to power on its
            # TPM. This is done. The subrack device detects that the TPM is now on.

            tile_device_state_changed_callback.assert_last_change_event(tango.DevState.ON)
            assert tile_device.state() == tango.DevState.ON
            assert subrack_device.tpm1PowerState == PowerState.ON

            # TurnOnTpm isn't directly called here so we have to get at it a bit
            # differently.
            args = lrc_result_changed_callback.get_next_call()
            assert "_PowerOnTpm" in args[0][1][0]
            assert args[0][1][1] == f'"Subrack TPM {tpm_id} turn on tpm task has completed"'

        def wait_for_tpm_initialisation():
            while tile_device.tileProgrammingState != "Initialised":
                time.sleep(0.5)
            assert tile_device.tileProgrammingState == "Initialised"

        def start_acquisition_tpm():
            ([return_code], [unique_id]) = tile_device.StartAcquisition(r"{}")
            print(f"return code = {return_code} | unique id = {unique_id}")

        def wait_for_tpm_synchronisation():
            while tile_device.tileProgrammingState != "Synchronised":
                time.sleep(0.5)
            assert tile_device.tileProgrammingState == "Synchronised"
                


        def configure_daq():
            """
            TODO: add functionality here when daq is released
            """
            
            # Configuration with non-default description in order 
            # to validate daq is configured
            daq_config = {
                "nof_antennas": 16, 
                "nof_channels": 512, 
                "nof_beams": 1, 
                "nof_polarisations": 2, 
                "nof_tiles": 1, 
                "nof_raw_samples": 32768, 
                "raw_rms_threshold": -1, 
                "nof_channel_samples": 1024, 
                "nof_correlator_samples": 1835008, 
                "nof_correlator_channels": 1, 
                "continuous_period": 0, 
                "nof_beam_samples": 42, 
                "nof_beam_channels": 384, 
                "nof_station_samples": 262144, 
                "append_integrated": True, 
                "sampling_time": 1.1325, 
                "sampling_rate": (800e6 / 2.0) * (32.0 / 27.0) / 512.0, 
                "oversampling_factor": 32.0 / 27.0, 
                "receiver_ports": "4660", 
                "receiver_interface": "eth0", 
                "receiver_ip": "8080", 
                "receiver_frame_size": 8500, 
                "receiver_frames_per_block": 32, 
                "receiver_nof_blocks": 256, 
                "receiver_nof_threads": 1, 
                "directory": ".", 
                "logging": True, 
                "write_to_disk": True, 
                "station_config": None, 
                "max_filesize": None, 
                "acquisition_duration": -1, 
                "acquisition_start_time": -1, 
                "description": "This is a test configuration"
                }
            return #TODO: remove when daq is implemented
            daq_device.Configure(daq_config)
            assert daq_device.configuration().items() == daq_config

        def start_daq():
            return #TODO: remove when daq is implemented
            task_callback=MockCallable()
            daq_device.Start(task_callback=task_callback, callbacks=[processed_data_callback])
            
            task_callback.assert_next_call(status=TaskStatus.QUEUED)
            task_callback.assert_next_call(status=TaskStatus.IN_PROGRESS)
            task_callback.assert_next_call(status=TaskStatus.COMPLETED)

        def send_data_from_tpm_to_daq():
            """
            TODO: finalise functionality here when daq is released
            """
            return #TODO: remove when daq is implemented
            #TODO decide on send data functionality
            tile_device.SendData()
            
            processed_data_callback.assert_next_call()

        configure_and_verify_callbacks()
        turn_on_subrack()
        turn_on_tpm()
        wait_for_tpm_initialisation()
        start_acquisition_tpm()
        wait_for_tpm_synchronisation()
        configure_daq()
        start_daq()
        send_data_from_tpm_to_daq()
