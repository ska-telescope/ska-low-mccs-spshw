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

import tango
from ska_control_model import AdminMode, PowerState
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


class TestSubrackTileIntegration:  # pylint: disable=too-few-public-methods
    """Integration test cases for interactions between subrack and tile."""

    def test_subrack_tile_integration(
        self: TestSubrackTileIntegration,
        subrack_device: tango.DeviceProxy,
        tile_device: tango.DeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test the integration of tile within subrack.

        Test that:

        * when MccsTile is turned on, the subrack supplies power to the
          TPM
        * when MccsTile is turned off, the subrack denies power to the
          TPM

        :param subrack_device: the subrack Tango device under test.
        :param tile_device: the tile Tango device under test.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert subrack_device.adminMode == AdminMode.OFFLINE
        assert tile_device.adminMode == AdminMode.OFFLINE

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

        # But at least now the tile device can turn its TPM on:
        _ = tile_device.On()

        # The tile device tells the subrack device
        # to tell its subrack to power on its TPM.
        # This is done, and the subrack device detects that the TPM is now on.
        change_event_callbacks["subrack_tpm_power_state"].assert_change_event(
            PowerState.ON
        )

        # The tile device receives this event too.
        # TODO: it transitions straight to ON without going through UNKNOWN. Why?
        change_event_callbacks["tile_state"].assert_change_event(tango.DevState.ON)

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
