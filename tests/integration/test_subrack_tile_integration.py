# pylint: disable=too-many-lines
#
# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains integration tests of tile-subrack interactions in MCCS."""
from __future__ import annotations

import datetime
import gc
import json
import time
import unittest
from typing import Any

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.tile import TileComponentManager, TileSimulator
from tests.test_tools import (
    execute_lrc_to_completion,
    wait_for_completed_command_to_clear_from_queue,
)

# TODO: Weird hang-at-garbage-collection bug
gc.disable()

RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


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
        "preadu_levels",
        "track_lrc_command",
        "generic_health_attribute",
        "daq_state",
        timeout=7.0,
    )


# pylint: disable=too-few-public-methods, too-many-arguments
class TestSubrackTileIntegration:
    """Integration test cases for a SPS station with subservient subrack and tile."""

    def test_communication(
        self: TestSubrackTileIntegration,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        pdu_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
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
        :param pdu_device: the pdu Tango device under test.
        :param tile_simulator: The mocked tile_simulator
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert subrack_device.adminMode == AdminMode.OFFLINE
        assert tile_device.adminMode == AdminMode.OFFLINE
        assert pdu_device.adminMode == AdminMode.OFFLINE
        assert daq_device.adminMode == AdminMode.OFFLINE

        daq_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["daq_state"],
        )
        change_event_callbacks["daq_state"].assert_change_event(tango.DevState.DISABLE)

        daq_device.adminMode = AdminMode.ONLINE
        pdu_device.adminMode = AdminMode.ONLINE

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
        tile_simulator.mock_on()
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        # The TPM may become connectable before the MccsSubrack device has fired a
        # change event. When the TPM is connectable and MccsSubrack reports
        # its power as anything but ON we are in a fault state (this is inconsistent).
        # As a result when connecting we transition to ON showing we can CONNECT,
        # followed by FAULT because of the transient inconsistency in state.
        # Finally when the state becomes consistent and we will transition back to ON.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.FAULT)
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
        tile_device.subscribe_event(
            "tileProgrammingState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
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
        sleep_time = 2.5
        time.sleep(sleep_time)
        final_time = tile_device.fpgasUnixTime[0]

        assert (final_time - initial_time) >= int(sleep_time)

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
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(subrack_device)

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
        assert tile_device.tileprogrammingstate == "Initialised"
        delay_time = 2  # seconds
        start_time = datetime.datetime.strftime(
            datetime.datetime.fromtimestamp(int(time.time()) + delay_time), RFC_FORMAT
        )
        [[result_code], [message]] = tile_device.StartAcquisition(
            json.dumps({"start_time": start_time})
        )
        assert result_code == ResultCode.QUEUED
        assert "StartAcquisition" in message.split("_")[-1]

        initial_frame = tile_device.currentFrame
        sleep_time = delay_time + 0.5  # seconds
        time.sleep(sleep_time)
        final_frame = tile_device.currentFrame
        assert final_frame > initial_frame

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
        execute_lrc_to_completion(
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
        time.sleep(1)
        result_str = tile_device.Get40GCoreConfiguration(json.dumps(arg))
        result = json.loads(result_str)
        # check is a subset
        assert config.items() <= result.items()

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
        expected = [2, 0, 0, 0, 0, 0, 0] + [0, 0, 0, 0, 0, 0, 0] * 47
        assert table == expected

    def test_preadu_levels(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        tile_component_manager: TileComponentManager,
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
        initial_level = tile_device.preadulevels
        tile_device.subscribe_event(
            "preaduLevels",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["preadu_levels"],
        )
        change_event_callbacks["preadu_levels"].assert_change_event(
            initial_level.tolist()
        )

        final_level = [i + 1.00 for i in initial_level]
        tile_device.preadulevels = final_level

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="PREADU_LEVELS")
        )
        change_event_callbacks["preadu_levels"].assert_change_event(final_level)

        # TANGO returns a ndarray.
        assert tile_device.preadulevels.tolist() == final_level  # type: ignore

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
        execute_lrc_to_completion(tile_device, "Initialise", None)

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="PPS_DELAY_CORRECTION")
        )
        time.sleep(0.3)
        final_corrections = tile_device.ppsDelayCorrection

        assert np.array_equal(final_corrections, tile_under_test_pps_delay)
        # assert tile_device.ppsDelay == tile_under_test_pps_delay

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        ("attribute", "initial_value", "alarm_value"),
        [
            (
                "fpga1Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA0"],
                77.0,
            ),
            (
                "fpga2Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA1"],
                77.0,
            ),
            (
                "boardTemperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["board"],
                96.0,
            ),
            (
                "ppsPresent",
                TileSimulator.TILE_MONITORING_POINTS["timing"]["pps"]["status"],
                False,
            ),
        ],
    )
    def test_health_attributes_alarms(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_component_manager: TileComponentManager,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        attribute: str,
        initial_value: Any,
        alarm_value: Any,
    ) -> None:
        """
        Test alarm is raised when attribute goes out of alarm threshold.

        This tests will check that when we set alarming values in the backend
        TileSimulator and force a poll the attribute corresponding to this will
        go into ALARM and the MccsTile device will go into ALARM.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param tile_component_manager: A component manager.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param subrack_device: the subrack Tango device under test.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param attribute: the name of the health attribute
        :param initial_value: the value that the TileSimulator initially has for this
            attribute
        :param alarm_value: A value that should raise an ALARM
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        # sleep to allow a poll
        time.sleep(0.5)

        sub_id = tile_device.subscribe_event(
            attribute,
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["generic_health_attribute"],
        )
        change_event_callbacks["generic_health_attribute"].assert_change_event(
            initial_value
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_VALID
        )

        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        # Set the alarming value in backend TileSimulator
        tile_device.SetHealthStructureInBackend(json.dumps({attribute: alarm_value}))

        change_event_callbacks["generic_health_attribute"].assert_change_event(
            alarm_value
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_ALARM
        )
        assert tile_device.state() == tango.DevState.ALARM
        tile_device.unsubscribe_event(sub_id)

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        ("attribute", "initial_value", "alarm_value"),
        [
            (
                "fpga1Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA0"],
                97.0,
            ),
            (
                "fpga2Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA1"],
                97.0,
            ),
            (
                "boardTemperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["board"],
                96.0,
            ),
        ],
    )
    def test_self_shutdown(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        attribute: str,
        initial_value: Any,
        alarm_value: Any,
    ) -> None:
        """
        Test alarm is raised when attribute goes out of alarm threshold.

        This tests will check that when we set alarming values in the backend
        TileSimulator and force a poll the attribute corresponding to this will
        go into ALARM and the MccsTile device will go into ALARM.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param subrack_device: the subrack Tango device under test.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param attribute: the name of the health attribute
        :param initial_value: the value that the TileSimulator initially has for this
            attribute
        :param alarm_value: A value that should raise an ALARM
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        sub_id = tile_device.subscribe_event(
            attribute,
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["generic_health_attribute"],
        )
        change_event_callbacks["generic_health_attribute"].assert_change_event(
            initial_value
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_VALID
        )

        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        # Set the alarming value in backend TileSimulator
        tile_device.SetHealthStructureInBackend(json.dumps({attribute: alarm_value}))

        # sleep to allow a poll

        change_event_callbacks["generic_health_attribute"].assert_change_event(
            alarm_value
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_ALARM
        )
        tile_device.unsubscribe_event(sub_id)

        # Confirm that the subrack reports the TPM is OFF.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )
        # Temperature attributes have a soft shutdown.
        # After overheating the Tile will turn off the port
        # and report the Power as OFF.
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)
        assert tile_device.state() == tango.DevState.OFF

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        ("attribute", "initial_value", "threshold_method"),
        [
            (
                "fpga1Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA0"],
                "fpga1TemperatureThresholds",
            ),
            (
                "fpga2Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA1"],
                "fpga2TemperatureThresholds",
            ),
            (
                "boardTemperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["board"],
                "boardTemperatureThresholds",
            ),
        ],
    )
    def test_setting_shutdown_temperatures(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        subrack_device: tango.DeviceProxy,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        attribute: str,
        initial_value: Any,
        threshold_method: str,
    ) -> None:
        """
        Test alarm is raised when attribute goes out of alarm threshold.

        This tests will check that when we set alarming values in the backend
        TileSimulator and force a poll the attribute corresponding to this will
        go into ALARM and the MccsTile device will go into ALARM.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param subrack_device: the subrack Tango device under test.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param attribute: the name of the health attribute
        :param initial_value: the value that the TileSimulator initially has for this
            attribute
        :param threshold_method: the method to read and write temperature thresholds.
        """
        self.setup_devices(
            tile_device,
            tile_simulator,
            subrack_device,
            daq_device,
            change_event_callbacks,
        )

        sub_id = tile_device.subscribe_event(
            attribute,
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["generic_health_attribute"],
        )
        change_event_callbacks["generic_health_attribute"].assert_change_event(
            initial_value
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_VALID
        )

        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

        # Set a max threshold below current temperature
        less_than_initial_value = initial_value - 1

        tile_device.SetAttributeThresholds(
            json.dumps({attribute: {"max_alarm": str(less_than_initial_value)}})
        )

        assert (
            tile_device.read_attribute(attribute).quality
            == tango.AttrQuality.ATTR_ALARM
        )
        tile_device.unsubscribe_event(sub_id)
        tile_device.SetHealthStructureInBackend(
            json.dumps({attribute: less_than_initial_value + 2})
        )

        # Confirm that the subrack reports the TPM is OFF.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )
        # Temperature attributes have a soft shutdown.
        # After overheating the Tile will turn off the port
        # and report the Power as OFF.
        change_event_callbacks["tile_state"].assert_change_event(
            tango.DevState.OFF, lookahead=2
        )

        assert float(tile_device.get_attribute_config(attribute).max_alarm) == float(
            less_than_initial_value
        )

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

    def test_tpm_discovery(
        self: TestMccsTileTpmDriver,
        tile_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test discovery of TPM state.

        This test was created to capture SKB-687. It will check:
        - Whether MccsTile can discover the correct TileProgrammingState
        - The subrack callback does not drive state when Synchronised.

        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        # We are mocking the TPM in a prexisting SYNCHRONISED state.
        # To check we do not re-initialise.
        tile_simulator.mock_on(lock=True)
        tile_simulator.program_fpgas("tpm_firmware.bit")
        tile_simulator.initialise()
        tile_simulator.start_acquisition(delay=0)
        tile_simulator._mocked_tpm = tile_simulator.tpm
        tile_simulator.tpm = None
        tile_simulator._is_cpld_connectable = False

        subrack_device.subscribe_event(
            "tpm1PowerState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_tpm_power_state"],
        )
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.UNKNOWN
        )

        subrack_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.OFF
        )
        subrack_device.PowerUpTpms()
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        tile_device.subscribe_event(
            "tileProgrammingState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")

        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Synchronised", lookahead=2, consume_nonmatches=True
        )
        change_event_callbacks["tile_programming_state"].assert_not_called()
