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
from typing import Generator

import pytest
import tango
from ska_control_model import AdminMode, PowerState, ResultCode
from ska_tango_testing.context import (
    TangoContextProtocol,
    ThreadedTestTangoContextManager,
)
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import DeviceProxy

# TODO: Weird hang-at-garbage-collection bug
gc.disable()


@pytest.fixture(name="tango_harness")
def tango_harness_fixture(
    subrack_name: str,
    subrack_address: tuple[str, int],
    tile_name: str,
) -> Generator[TangoContextProtocol, None, None]:
    """
    Return a Tango harness against which to run tests of the deployment.

    :param subrack_name: the name of the subrack Tango device
    :param subrack_address: the host and port of the subrack
    :param tile_name: the name of the tile Tango device

    :yields: a tango context.
    """
    subrack_ip, subrack_port = subrack_address

    context_manager = ThreadedTestTangoContextManager()
    context_manager.add_device(
        subrack_name,
        "ska_low_mccs_spshw.MccsSubrack",
        SubrackIp=subrack_ip,
        SubrackPort=subrack_port,
        UpdateRate=1.0,
        LoggingLevelDefault=5,
    )
    context_manager.add_device(
        tile_name,
        "ska_low_mccs_spshw.MccsTile",
        TileId=1,
        SubrackFQDN=subrack_name,
        SubrackBay=1,
        AntennasPerTile=2,
        SimulationConfig=1,
        TestConfig=1,
        TpmIp="10.0.10.201",
        TpmCpldPort=10000,
        TpmVersion="tpm_v1_6",
        LoggingLevelDefault=5,
    )
    with context_manager as context:
        yield context


@pytest.fixture(name="subrack_device")
def subrack_device_fixture(
    tango_harness: TangoContextProtocol,
    subrack_name: str,
) -> DeviceProxy:
    """
    Return the subrack Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param subrack_name: name of the subrack Tango device.

    :return: the subrack Tango device under test.
    """
    return tango_harness.get_device(subrack_name)


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    tango_harness: TangoContextProtocol,
    tile_name: str,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param tango_harness: a test harness for Tango devices.
    :param tile_name: name of the tile Tango device.

    :return: the tile Tango device under test.
    """
    return tango_harness.get_device(tile_name)


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
        timeout=2.0,
    )


class TestSubrackTileIntegration:  # pylint: disable=too-few-public-methods
    """Integration test cases for a SPS station with subservient subrack and tile."""

    @pytest.mark.xfail
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

        # Now the tile device can turn its TPM on,
        # but first let's subscribe to change events on command status,
        # so that we can track the status of the command
        tile_device.subscribe_event(
            "longRunningCommandStatus",
            tango.EventType.CHANGE_EVENT,
            change_event_callbacks["tile_command_status"],
        )
        change_event_callbacks["tile_command_status"].assert_change_event(None)

        ([result_code], [on_command_id]) = tile_device.On()
        assert result_code == ResultCode.QUEUED

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
