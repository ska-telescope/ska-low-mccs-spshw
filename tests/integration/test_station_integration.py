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

import pytest
import tango
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.tile import TileSimulator

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
        "station_state",
        "subrack_state",
        "tile_state",
        "tile_programming_state",
        "sps_station_command_status",
        "sps_adc_power",
        timeout=15.0,
    )


def test_station(
    sps_station_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
    tile_device: tango.DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> None:
    """
    Test SPS station integration with subservient subrack and tile.

    :param sps_station_device: the station Tango device under test.
    :param subrack_device: the subrack Tango device under test.
    :param tile_device: the tile Tango device under test.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    assert sps_station_device.adminMode == AdminMode.OFFLINE
    assert subrack_device.adminMode == AdminMode.OFFLINE
    assert tile_device.adminMode == AdminMode.OFFLINE

    # Since the devices are in adminMode OFFLINE,
    # they are not even trying to monitor and control their components,
    # so they each report state as DISABLE.
    sps_station_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["station_state"],
    )
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.DISABLE)
    subrack_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_state"],
    )
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.DISABLE)
    tile_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_state"],
    )
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)

    sps_station_device.adminMode = AdminMode.ONLINE

    change_event_callbacks["station_state"].assert_change_event(tango.DevState.UNKNOWN)

    # Station stays in UNKNOWN state
    # because subrack and tile devices are still OFFLINE
    change_event_callbacks["station_state"].assert_not_called()

    tile_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)

    # Tile and station both stay in UNKNOWN state
    # because subrack is still OFFLINE
    change_event_callbacks["tile_state"].assert_not_called()
    change_event_callbacks["station_state"].assert_not_called()

    subrack_device.adminMode = AdminMode.ONLINE
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.UNKNOWN)
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.ON)

    # Now that subrack is ONLINE, it reports itself ON, and the TPM to be OFF,
    # so MccsTile reports itself OFF
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

    # When the subracks are on but the tiles are off,
    # the station is in STANDBY.
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.STANDBY)
    change_event_callbacks["station_state"].assert_not_called()

    tile_device.subscribe_event(
        "tileProgrammingState",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_programming_state"],
    )
    change_event_callbacks["tile_programming_state"].assert_change_event("Off")

    tile_device.On()

    change_event_callbacks["tile_programming_state"].assert_change_event(
        "NotProgrammed"
    )
    change_event_callbacks["tile_programming_state"].assert_change_event("Programmed")
    change_event_callbacks["tile_programming_state"].assert_change_event("Initialised")
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
    change_event_callbacks["station_state"].assert_change_event(tango.DevState.ON)


class TestStationTileIntegration:
    """Test the integration between the Station and the Tile."""

    def test_initialise_can_execute(
        self: TestStationTileIntegration,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the sps station Initialise function executes.

        This is a very simple test just just to see that the TileSimulator
        starts counting once turned on and initialised.

        TODO: Initialise does a huge number of tasks.
        This test only check the initialise command can complete,
        it does not check in any specifics.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        test_station(
            sps_station_device, subrack_device, tile_device, change_event_callbacks
        )

        sps_station_device.subscribe_event(
            "longRunningCommandStatus",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["sps_station_command_status"],
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(())

        ([result_code], [initialise_id]) = sps_station_device.Initialise()

        assert result_code == ResultCode.QUEUED

        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "QUEUED")
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "IN_PROGRESS")
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "COMPLETED")
        )

    def test_adc_power_change(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the sps station adcPower gets updates.

        This test checks that a change in the backend `tile_simulator`
        attribute `adc_rms` is propagated all the way to the `SpsStation`.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        test_station(
            sps_station_device, subrack_device, tile_device, change_event_callbacks
        )

        sps_station_device.subscribe_event(
            "longRunningCommandStatus",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["sps_station_command_status"],
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(())

        ([result_code], [initialise_id]) = sps_station_device.Initialise()

        assert result_code == ResultCode.QUEUED

        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "QUEUED")
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "IN_PROGRESS")
        )
        change_event_callbacks["sps_station_command_status"].assert_change_event(
            (initialise_id, "COMPLETED")
        )

        sps_station_device.subscribe_event(
            "adcPower",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["sps_adc_power"],
        )
        change_event_callbacks["sps_adc_power"].assert_change_event(Anything)

        # Set the value in the backend TileSimulator.
        initial_adc_powers = [12.0] + [0.0] * 31
        tile_simulator._adc_rms = initial_adc_powers

        # Force a poll on the backend simulator.
        tile_device.UpdateAttributes()

        # This will cause the Tile to push a change event.
        # SpsStation is subscribed to this attribute and
        # Should push a change event itself.
        change_event_callbacks["sps_adc_power"].assert_change_event(initial_adc_powers)

        # Check with different values.
        final_adc_powers = [24.0] + [24.0] * 31
        tile_simulator._adc_rms = final_adc_powers
        tile_device.UpdateAttributes()
        change_event_callbacks["sps_adc_power"].assert_change_event(final_adc_powers)
