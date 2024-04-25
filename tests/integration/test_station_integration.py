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
import time
import unittest

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

from ska_low_mccs_spshw.tile import TileComponentManager, TileSimulator
from tests.test_tools import (
    execute_lrc_to_completion,
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
        "station_state",
        "subrack_state",
        "tile_state",
        "tile_programming_state",
        "sps_station_command_status",
        "sps_adc_power",
        "tile_static_delays",
        "tile_preadu_levels",
        "tile_csp_rounding",
        "tile_channeliser_rounding",
        "track_lrc_command",
        "daq_state",
        timeout=8.0,
    )


def test_initialise_can_execute(
    sps_station_device: tango.DeviceProxy,
    subrack_device: tango.DeviceProxy,
    tile_device: tango.DeviceProxy,
    tile_simulator: TileSimulator,
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
    :param tile_simulator: the backend tile simulator. This is
        what tile_device is observing.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    """
    subrack_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["subrack_state"],
    )
    change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.DISABLE)
    subrack_device.adminMode = AdminMode.ONLINE

    change_event_callbacks["subrack_state"].assert_change_event(
        tango.DevState.ON, lookahead=2
    )
    assert tile_device.adminMode == AdminMode.OFFLINE
    tile_device.subscribe_event(
        "state",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_state"],
    )
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)
    tile_device.subscribe_event(
        "tileProgrammingState",
        tango.EventType.CHANGE_EVENT,
        change_event_callbacks["tile_programming_state"],
    )

    change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")

    # Turn adminMode ONLINE with the TPM mocked to be OFF
    tile_simulator.mock_off()
    tile_device.adminMode = AdminMode.ONLINE

    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)
    change_event_callbacks["tile_programming_state"].assert_change_event("Off")

    tile_device.On()

    change_event_callbacks["tile_programming_state"].assert_change_event(
        "NotProgrammed",
        lookahead=2,
        consume_nonmatches=True,
    )

    change_event_callbacks["tile_programming_state"].assert_change_event("Initialised")
    change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

    wait_for_completed_command_to_clear_from_queue(tile_device)


class TestStationTileIntegration:
    """Test the integration between the Station and the Tile."""

    def turn_station_on(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test SPS station integration with subservient subrack and tile.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert sps_station_device.adminMode == AdminMode.OFFLINE
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
        # Since the devices are in adminMode OFFLINE,
        # they are not even trying to monitor and control their components,
        # so they each report state as DISABLE.
        tile_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_state"],
        )
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.DISABLE)

        sps_station_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["station_state"],
        )
        change_event_callbacks["station_state"].assert_change_event(
            tango.DevState.DISABLE
        )
        subrack_device.subscribe_event(
            "state",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["subrack_state"],
        )
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.DISABLE
        )
        sps_station_device.adminMode = AdminMode.ONLINE

        change_event_callbacks["station_state"].assert_change_event(
            tango.DevState.UNKNOWN
        )
        tile_device.subscribe_event(
            "tileProgrammingState",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")

        # Station stays in UNKNOWN state
        # because subrack and tile devices are still OFFLINE
        tile_simulator.mock_off()
        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.UNKNOWN)

        # Tile and station both stay in UNKNOWN state
        # because subrack is still OFFLINE
        change_event_callbacks["tile_state"].assert_not_called()
        change_event_callbacks["station_state"].assert_not_called()

        subrack_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["subrack_state"].assert_change_event(
            tango.DevState.UNKNOWN
        )
        change_event_callbacks["subrack_state"].assert_change_event(tango.DevState.ON)

        # Now that subrack is ONLINE, it reports itself ON, and the TPM to be OFF,
        # so MccsTile reports itself OFF
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.OFF)

        # When the subracks are on but the tiles are off,
        # the station is in STANDBY.
        change_event_callbacks["station_state"].assert_change_event(
            tango.DevState.STANDBY
        )
        change_event_callbacks["station_state"].assert_not_called()
        # The Subrack will be ONLINE and therefore will know the state of
        # the port the TPM is on.
        change_event_callbacks["tile_programming_state"].assert_change_event("Off")

        tile_device.On()
        # Depending where we are on the poll when on is executed
        # we may be Unconnected or NotProgrammed, hence the lookahead of 2.
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "NotProgrammed",
            lookahead=2,
            consume_nonmatches=True,
        )
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Initialised"
        )

        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)
        change_event_callbacks["station_state"].assert_change_event(tango.DevState.ON)

        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    def test_initialise_can_execute(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        daq_device: tango.DeviceProxy,
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
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )
        # Check that the initialise LRC executes to COMPLETION
        execute_lrc_to_completion(
            change_event_callbacks, sps_station_device, "Initialise", None
        )
        assert tile_device.tileProgrammingState == "Initialised"
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    def test_pps_delay(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test that pps delays can be set and read from station to tile.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        initial_corrections = sps_station_device.ppsDelayCorrections

        # set a pps Correction to apply
        tile_under_test_pps_delay = 12
        desired_pps_corrections = [0] * 16
        desired_pps_corrections[0] = tile_under_test_pps_delay

        sps_station_device.ppsDelayCorrections = desired_pps_corrections

        # This pps delay correction is only applied during initialisation.

        pps_corrections_before_initialisation = sps_station_device.ppsDelayCorrections
        assert (pps_corrections_before_initialisation == initial_corrections).all()

        # Call initialise
        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
        )
        # Force a poll to get the initial values.
        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="PPS_DELAY_CORRECTION")
        )
        time.sleep(1)
        final_corrections = sps_station_device.ppsDelayCorrections

        assert np.array_equal(final_corrections, desired_pps_corrections)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    def test_adc_power_change(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
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
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
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

        # This will cause the Tile to push a change event.
        # SpsStation is subscribed to this attribute and
        # Should push a change event itself.
        change_event_callbacks["sps_adc_power"].assert_change_event(initial_adc_powers)

        # Check with different values.
        final_adc_powers = [24.0] + [24.0] * 31
        tile_simulator._adc_rms = final_adc_powers

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="ADC_RMS")
        )
        change_event_callbacks["sps_adc_power"].assert_change_event(final_adc_powers)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    def test_static_delay(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
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
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
        )

        tile_device.subscribe_event(
            "staticTimeDelays",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_static_delays"],
        )
        change_event_callbacks["tile_static_delays"].assert_change_event(Anything)

        # Set the value in the backend TileSimulator.
        initial_static_delays = np.array([12.5] + [0.0] * 31)
        tile_simulator.set_time_delays(initial_static_delays.tolist())

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="STATIC_DELAYS")
        )
        # This will cause the Tile to push a change event.

        change_event_callbacks["tile_static_delays"].assert_change_event(
            initial_static_delays.tolist()
        )

        time.sleep(0.1)
        assert np.array_equal(
            sps_station_device.staticTimeDelays, initial_static_delays
        )

        # Set new value from SpsStation
        final_static_delays = np.array([1.25] + [0.0] * 31)
        sps_station_device.staticTimeDelays = final_static_delays

        change_event_callbacks["tile_static_delays"].assert_change_event(
            final_static_delays.tolist()
        )
        time.sleep(0.1)

        assert np.array_equal(sps_station_device.staticTimeDelays, final_static_delays)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    # pylint: disable-next=too-many-arguments
    def test_sps_preadu_levels_coherent_with_tile_simulator(
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the sps station preadulevels gets updates.

        This test checks that a change in the backend `tile_simulator`
        attribute `preadulevels` is propagated all the way to the `SpsStation`.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
        )

        # Initialise values in the backend TileSimulator and forces update
        tile_simulator.set_preadu_levels([0.0] * 32)

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="PREADU_LEVELS")
        )
        # Set the value in the backend TileSimulator.
        initial_preadu_levels = [12.0] * 32
        tile_simulator.set_preadu_levels(initial_preadu_levels)

        # Subscibe to change events on the preaduLevels attribute.
        tile_device.subscribe_event(
            "preaduLevels",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_preadu_levels"],
        )
        change_event_callbacks["tile_preadu_levels"].assert_change_event(Anything)

        # Force a poll on the backend simulator.

        assert sps_station_device.preaduLevels.tolist() != initial_preadu_levels

        # This will cause the Tile to push a change event.
        change_event_callbacks["tile_preadu_levels"].assert_change_event(
            initial_preadu_levels
        )

        # Check the station updates its own map.
        assert sps_station_device.preaduLevels.tolist() == initial_preadu_levels

        # Now set the value in `SpsStation`, check `MccsTile` and `TileSimulator`,
        # Finally check `SpsStation` attribute value.
        desired_preadu_levels = np.array([24.0] * 32)
        sps_station_device.preaduLevels = desired_preadu_levels
        # Not equal because we need the MccsTile to change value.
        assert not np.array_equal(
            sps_station_device.preaduLevels, desired_preadu_levels
        )

        change_event_callbacks["tile_preadu_levels"].assert_change_event(
            desired_preadu_levels.tolist()
        )
        assert tile_simulator.get_preadu_levels() == desired_preadu_levels.tolist()

        # Check the station updates its own map.
        time.sleep(0.1)
        assert np.array_equal(sps_station_device.preaduLevels, desired_preadu_levels)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    # pylint: disable-next=too-many-arguments
    def test_csp_rounding(
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the sps station cspRounding gets updates.

        This test checks that a change in the backend `tile_simulator`
        attribute `cspRounding` is propagated all the way to the `SpsStation`.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
        )
        # Subscibe to change events on the preaduLevels attribute.
        tile_device.subscribe_event(
            "cspRounding",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_csp_rounding"],
        )
        change_event_callbacks["tile_csp_rounding"].assert_change_event(Anything)

        csp_to_check = np.array([5] * 384)
        tile_device.cspRounding = csp_to_check

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="CSP_ROUNDING")
        )
        # This will cause the Tile to push a change event.
        change_event_callbacks["tile_csp_rounding"].assert_change_event(
            csp_to_check.tolist()
        )
        # mock failure
        tile_simulator.is_csp_write_successful = False

        tile_device.cspRounding = [10] * 384

        change_event_callbacks["tile_csp_rounding"].assert_not_called()

        # Check that the station agrees on the last value pushed by tile.
        assert np.array_equal(sps_station_device.cspRounding, csp_to_check)
        tile_simulator.is_csp_write_successful = True

        # check we can set from SpsStation.
        value_to_write = np.array([10] * 384)
        sps_station_device.cspRounding = value_to_write

        change_event_callbacks["tile_csp_rounding"].assert_change_event(
            value_to_write.tolist()
        )

        assert np.array_equal(sps_station_device.cspRounding, value_to_write)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)

    def test_channeliser_rounding(  # pylint: disable=too-many-arguments
        self: TestStationTileIntegration,
        tile_device: tango.DeviceProxy,
        sps_station_device: tango.DeviceProxy,
        subrack_device: tango.DeviceProxy,
        tile_simulator: TileSimulator,
        tile_component_manager: TileComponentManager,
        daq_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the sps station cspRounding gets updates.

        This test checks that a change in the backend `tile_simulator`
        attribute `cspRounding` is propagated all the way to the `SpsStation`.

        :param sps_station_device: the station Tango device under test.
        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param tile_simulator: the backend tile simulator. This is
            what tile_device is observing.
        :param tile_component_manager: A component manager.
        :param daq_device: the Daq Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        self.turn_station_on(
            sps_station_device,
            subrack_device,
            tile_device,
            tile_simulator,
            daq_device,
            change_event_callbacks,
        )

        execute_lrc_to_completion(
            change_event_callbacks, tile_device, "Initialise", None
        )
        tile_device.channeliserRounding = np.array([10] * 512)

        request_provider = tile_component_manager._request_provider
        assert request_provider is not None
        request_provider.get_request = (  # type: ignore[method-assign]
            unittest.mock.Mock(return_value="CHANNELISER_ROUNDING")
        )
        # Subscibe to change events on the preaduLevels attribute.
        tile_device.subscribe_event(
            "channeliserRounding",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_channeliser_rounding"],
        )
        change_event_callbacks["tile_channeliser_rounding"].assert_change_event(
            [10] * 512
        )

        channeliser_rounding_to_set = np.array([5] * 512)
        sps_station_device.SetChanneliserRounding(channeliser_rounding_to_set)
        zero_results = np.zeros((15, 512))

        # This will cause the Tile to push a change event.
        change_event_callbacks["tile_channeliser_rounding"].assert_change_event(
            channeliser_rounding_to_set.tolist(), lookahead=2, consume_nonmatches=True
        )

        # Check that the single Tile in this test context is set
        # all others report the default `0.` values
        channeliser_rounding_to_check: np.ndarray = np.concatenate(
            (np.array([channeliser_rounding_to_set]), zero_results)
        )

        # Check that the station agrees on the lase value pushed by tile.
        assert np.array_equal(
            sps_station_device.channeliserRounding, channeliser_rounding_to_check
        )
        wait_for_completed_command_to_clear_from_queue(tile_device)
        wait_for_completed_command_to_clear_from_queue(sps_station_device)
