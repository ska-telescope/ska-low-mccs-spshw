# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import gc
import json
import time
import unittest

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.tile import TileComponentManager, TileSimulator
from tests.test_tools import (
    execute_lrc_to_complettion,
    wait_for_completed_command_to_clear_from_queue,
)

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="change_event_callbacks")
def change_event_callbacks_fixture() -> MockTangoEventCallbackGroup:
    """
    Return a dictionary of callables to be used as Tango change event callbacks.

    :return: a dictionary of callables to be used as tango change event
        callbacks.
    """
    return MockTangoEventCallbackGroup(
        "subrack_state",
        "subrack_result",
        "subrack_tpm_power_state",
        "tile_state",
        "tile_command_status",
        "tile_programming_state",
        "pps_present",
        "track_lrc_command",
        "daq_state",
        timeout=5.0,
    )


# pylint: disable=too-few-public-methods, too-many-arguments
class TestSubrackTileIntegration:
    """Integration test cases for a SPS station with subservient subrack and tile."""

    def test_communication(
        self: TestSubrackTileIntegration,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        tile_simulator: tango.Deviceproxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the integration of tile within subrack.

        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert subrack_device.adminMode == AdminMode.OFFLINE
        assert tile_device.adminMode == AdminMode.OFFLINE
        assert daq_device.adminMode == AdminMode.OFFLINE

        daq_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["daq_state"],
        )
        change_event_callbacks["daq_state"].assert_change_event(tango.DevState.DISABLE)

        daq_device.adminMode = AdminMode.ONLINE

        change_event_callbacks["daq_state"].assert_change_event(
            tango.DevState.ON, lookahead=2
        )

        # Since the subrack device is in adminMode OFFLINE,
        # it is not even trying to monitor and control its subrack,
        # so it reports its state as DISABLE,
        # and its TPM power states as UNKNOWN.
        subrack_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_state"],
        )
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.DISABLE
        )

        subrack_device.subscribe_event(
            "tpm1PowerState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_tpm_power_state"],
        )
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.UNKNOWN
        )

        # Since the tile device is in adminMode OFFLINE,
        # it is not even trying to monitor and control its subrack,
        # so it reports its state as DISABLE.
        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )

        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
        change_event_callbacks["tile_state"].assert_not_called()

        tile_simulator.mock_off()
        tile_device.adminMode = AdminMode.ONLINE

        # Before the tile device tries to connect with its TPM,
        # it needs to find out from its subrack whether the TPM is even turned on.
        # So it subscribes to change events from its subrack's corresponding
        # TPM power state attribute.
        # The subrack reports that the TPM power state is UNKNOWN,
        # so the tile remains in UNKNOWN state.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)
        change_event_callbacks["tile_state"].assert_not_called()

        subrack_device.adminMode = AdminMode.ONLINE

        # The subrack device tries to establish a connection to its upstream power
        # supply device.
        # Until this connection is established, it is in UNKNOWN state.
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.UNKNOWN
        )

        # Once the subrack device is connected to its subrack,
        # it transitions to ON state.
        # It is also now in a position to report on whether its TPMs are on or off.
        change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.ON)
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )

        # The tile device receives the same event,
        # so it transitions to OFF state.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

        # Now the tile device can turn its TPM on,
        # but first let's subscribe to change events on command status,
        # so that we can track the status of the command
        tile_device.subscribe_event(
            "longRunningCommandStatus",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_command_status"],
        )
        change_event_callbacks["tile_command_status"].assert_change_event(())

        ([result_code], [on_command_id]) = tile_device.On()
        assert result_code == ResultCode.QUEUED
        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "STAGING")
        )
        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "QUEUED")
        )
        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "IN_PROGRESS")
        )

        # The tile device tells the subrack device
        # to tell its subrack to power on its TPM.
        # This is done, and the subrack device detects that the TPM is now on.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        # The tile device receives this event too.
        # TODO: it transitions straight to ON without going through UNKNOWN. Why?
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "COMPLETED")
        )

        # Now let's turn it off.
        _ = tile_device.Off()

        # The tile device tells the subrack device
        # to tell its subrack to power off its TPM.
        # This is done. The subrack device detects that the TPM is now off.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )

        # The tile device receives this event too. It transitions to OFF.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

        # Now we power on the TPM using the subrack,
        # to check that the tile response is responsible to "spontaneous" changes.
        _ = subrack_device.PowerOnTpm(1)

        # The subrack device tells the subrack to turn the TPM on. It does so.
        # The subrack device detects that the TPM is on.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        # The tile device receives this event too.
        # TODO: it transitions straight to ON without going through UNKNOWN. Why?
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        # Now we power off all the TPMs using the subrack,
        # to check that the tile response is responsible to "spontaneous" changes.
        _ = subrack_device.PowerDownTpms()

        # The subrack device tells the subrack to turn all the TPMs off.
        # It does so. The subrack device detects that the TPM is off.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )

        # The tile device receives this event too. It transitions to OFF.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)
        change_event_callbacks["tile_state"].assert_not_called()
        wait_for_completed_command_to_clear_from_queue(tile_device)


class TestMccsTileTpmDriver:
    """This class is for testing the MccsTile using the TileSimulator."""

    # pylint: disable=too-many-arguments
    def setup_devices(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Set devices in a commonly desired state.

        Consider generalising this to expand for different setups.

        # FINAL_CONFIGURATION
        tile_device.adminMode == AdminMode.ONLINE
        tile_device.state == tango.DevState.ON
        subrack_device.adminMode == AdminMode.ONLINE
        subrack_device.state == tango.DevState.ON

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert subrack_device.adminMode == AdminMode.OFFLINE
        assert tile_device.adminMode == AdminMode.OFFLINE
        assert daq_device.adminMode == AdminMode.OFFLINE

        daq_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["daq_state"],
        )
        change_event_callbacks["daq_state"].assert_change_event(tango.DevState.DISABLE)

        daq_device.adminMode = AdminMode.ONLINE

        change_event_callbacks["daq_state"].assert_change_event(
            tango.DevState.ON, lookahead=2
        )

        # Since the subrack device is in adminMode OFFLINE,
        # it is not even trying to monitor and control its subrack,
        # so it reports its state as DISABLE,
        # and its TPM power states as UNKNOWN.
        subrack_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_state"],
        )
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.DISABLE
        )

        subrack_device.subscribe_event(
            "tpm1PowerState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_tpm_power_state"],
        )
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.UNKNOWN
        )

        # Since the tile device is in adminMode OFFLINE,
        # it is not even trying to monitor and control its TPM,
        # so it reports its state as DISABLE.
        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )

        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
        change_event_callbacks["tile_state"].assert_not_called()
        tile_simulator.mock_off()
        tile_device.adminMode = AdminMode.ONLINE

        # Before the tile device tries to connect with its TPM,
        # it needs to find out from its subrack whether the TPM is even turned on.
        # So it subscribes to change events from its subrack's corresponding
        # TPM power state attribute.
        # The subrack reports that the TPM power state is UNKNOWN,
        # so the tile remains in UNKNOWN state.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)
        change_event_callbacks["tile_state"].assert_not_called()
        subrack_device.adminMode = AdminMode.ONLINE

        # The subrack device tries to establish a connection to its upstream power
        # supply device.
        # Until this connection is established, it is in UNKNOWN state.
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.UNKNOWN
        )

        # Once the subrack device is connected to its subrack,
        # it transitions to ON state.
        # It is also now in a position to report on whether its TPMs are on or off.
        change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.ON)
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )

        # The tile device receives the same event,
        # so it transitions to OFF state.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

        # Now the tile device can turn its TPM on,
        # but first let's subscribe to change events on command status,
        # so that we can track the status of the command
        tile_device.subscribe_event(
            "longRunningCommandStatus",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_command_status"],
        )
        change_event_callbacks["tile_command_status"].assert_change_event(())

        tile_device.subscribe_event(
            "tileProgrammingState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Off", lookahead=2, consume_nonmatches=True
        )
        ([result_code], [on_command_id]) = tile_device.On()
        assert result_code == ResultCode.QUEUED

        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "STAGING")
        )
        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "QUEUED")
        )
        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "IN_PROGRESS")
        )
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "NotProgrammed", lookahead=2, consume_nonmatches=True
        )

        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Programmed"
        )
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Initialised"
        )
        # check that the fpga time is moving.
        initial_time = tile_device.fpgasUnixTime[0]
        sleep_time = 2
        time.sleep(sleep_time)
        final_time = tile_device.fpgasUnixTime[0]

        assert (final_time - initial_time) >= sleep_time - 1

        # The tile device tells the subrack device
        # to tell its subrack to power on its TPM.
        # This is done, and the subrack device detects that the TPM is now on.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        # The tile device receives this event too.
        # TODO: it transitions straight to ON without going through UNKNOWN. Why?
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        change_event_callbacks["tile_command_status"].assert_change_event(
            (on_command_id, "COMPLETED")
        )
        change_event_callbacks["tile_command_status"].assert_not_called()
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_start_acquisition(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test StartAcquisition.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        delay_time = 2  # seconds
        [[result_code], [message]] = tile_device.StartAcquisition(
            json.dumps({"delay": delay_time})
        )
        assert result_code == ResultCode.QUEUED
        assert "StartAcquisition" in message.split("_")[-1]

        initial_frame = tile_device.currentFrame
        time.sleep(delay_time - 1)
        final_frame = tile_device.currentFrame
        assert initial_frame == final_frame == 0

        time.sleep(1)

        initial_frame = tile_device.currentFrame
        sleep_time = 1  # seconds
        time.sleep(sleep_time)
        final_frame = tile_device.currentFrame
        assert final_frame > initial_frame
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_send_data_samples(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test SendDataSamples can only be called if startAcquisition has been.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        with pytest.raises(
            tango.DevFailed,
            match="ValueError: Cannot send data before StartAcquisition",
        ):
            [[result_code], [message]] = tile_device.SendDataSamples(
                json.dumps({"data_type": "beam"})
            )
        change_event_callbacks["tile_command_status"].assert_not_called()

        # Start Acquisition
        delay_time = 2
        execute_lrc_to_complettion(
            change_event_callbacks,
            tile_device,
            "StartAcquisition",
            json.dumps({"delay": delay_time}),
        )

        # Wait for synchronisation
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Synchronised"
        )

        [[_], [command_id]] = tile_device.SendDataSamples(
            json.dumps({"data_type": "raw"})
        )
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_configure_40g_core(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for configuring the 40G cores.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        config = {
            "core_id": 1,
            "arp_table_entry": 0,
            "source_ip": "10.0.0.98",
            "destination_ip": "10.0.0.99",
        }

        tile_device.Configure40GCore(json.dumps(config))

        arg = {
            "core_id": 1,
            "arp_table_entry": 0,
        }
        time.sleep(2)
        result_str = tile_device.Get40GCoreConfiguration(json.dumps(arg))
        result = json.loads(result_str)
        # check is a subset
        assert config.items() <= result.items()
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_configure_40g_core_with_bad_configuration(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for Configure40gCore unhappy case.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        # Load a bad configuration.
        bad_config = {
            "core_id": 4,
            "arp_table_entry": 0,
            "source_ip": "10.0.0.98",
            "destination_ip": "10.0.0.99",
        }

        tile_device.Configure40GCore(json.dumps(bad_config))

        arg = {
            "core_id": 4,
            "arp_table_entry": 0,
        }
        with pytest.raises(
            tango.DevFailed,
            match="ValueError: Invalid core id or arp table id specified",
        ):
            tile_device.Get40GCoreConfiguration(json.dumps(arg))
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_configure_beamformer(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for configuring the beamformer.

        Note: This is a very basic test testing the happy case.
        consider unhappy cases and more complex scenarios.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        tile_device.ConfigureStationBeamformer(
            json.dumps(
                {
                    "start_channel": 2,
                    "n_channels": 8,
                    "is_first": True,
                    "is_last": False,
                }
            )
        )

        table = list(tile_device.beamformerTable)
        expected = [2, 0, 0, 0, 0, 0, 0]
        assert table == expected
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_preadu_levels(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the preadu_levels.

        :param daq_device: the Daq Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        initial_level = tile_device.preadulevels

        final_level = [i + 1.00 for i in initial_level]
        tile_device.preadulevels = final_level
        time.sleep(14)
        # TANGO returns a ndarray.
        assert tile_device.preadulevels.tolist() == final_level  # type: ignore
        wait_for_completed_command_to_clear_from_queue(tile_device)

    # pylint: disable=too-many-arguments
    def test_pps_present(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test alarm is raised when pps is disconnected.

        This tests from the TileSimulator to the Tango interface.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param subrack_device: the subrack Tango device under test.
        :param daq_device: the Daq Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        tile_device.subscribe_event(
            "ppsPresent",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["pps_present"],
        )
        change_event_callbacks["pps_present"].assert_change_event(True)
        assert (
            tile_device.read_attribute("ppspresent").quality
            == tango.AttrQuality.ATTR_VALID
        )
        tile_simulator._tile_health_structure["timing"]["pps"]["status"] = False

        change_event_callbacks["pps_present"].assert_change_event(False)
        assert (
            tile_device.read_attribute("ppspresent").quality
            == tango.AttrQuality.ATTR_ALARM
        )
        assert tile_device.state() == tango.DevState.ALARM
        wait_for_completed_command_to_clear_from_queue(tile_device)

    # pylint: disable=too-many-arguments
    def test_pps_delay(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        daq_device: tango.DeviceProxy,
        tile_component_manager: TileComponentManager,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test alarm is raised when pps is disconnected.

        This tests from the TileSimulator to the Tango interface.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param subrack_device: the subrack Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param daq_device: the Daq Tango device under test.
        :param tile_component_manager: A component manager.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        # set a pps Correction to apply
        tile_under_test_pps_delay = 12

        tile_device.ppsDelayCorrection = tile_under_test_pps_delay

        # This pps delay correction is only applied during initialisation.
        execute_lrc_to_complettion(
            change_event_callbacks, tile_device, "Initialise", None
        )

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value=("PPS_DELAY_CORRECTION", None))
        )
        time.sleep(0.2)
        final_corrections = tile_device.ppsDelayCorrection

        assert np.array_equal(final_corrections, tile_under_test_pps_delay)
        # assert tile_device.ppsDelay == tile_under_test_pps_delay
        wait_for_completed_command_to_clear_from_queue(tile_device)

    def test_tile_state_rediscovery(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test tile can be turned OFFLINE and ONLINE and rediscover state.

        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)

        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
        assert tile_device.state() == tango.DevState.ON
        change_event_callbacks["tile_state"].assert_not_called()
        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)

        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_state"].assert_change_event(
            tango.DevState.ON, lookahead=2, consume_nonmatches=True
        )
        tile_device.off()
        change_event_callbacks["tile_state"].assert_change_event(
            tango.DevState.OFF, lookahead=2, consume_nonmatches=True
        )
        assert tile_device.state() == tango.DevState.OFF
        change_event_callbacks["tile_state"].assert_not_called()
        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
        change_event_callbacks["tile_state"].assert_not_called()

        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_state"].assert_change_event(
            tango.DevState.OFF, lookahead=2, consume_nonmatches=True
        )
        change_event_callbacks["tile_state"].assert_not_called()
        tile_device.on()

        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
        assert tile_device.state() == tango.DevState.ON
        change_event_callbacks["tile_state"].assert_not_called()
        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
