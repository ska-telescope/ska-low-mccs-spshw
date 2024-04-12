# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests for MccsTile."""
from __future__ import annotations

import copy
import gc
import itertools
import json
import time
import unittest.mock
from typing import Any, Iterator, Optional

import numpy as np
import pytest
from ska_control_model import (
    AdminMode,
    CommunicationStatus,
    HealthState,
    PowerState,
    ResultCode,
    TaskStatus,
)
from ska_low_mccs_common import MccsDeviceProxy
from ska_tango_testing.mock.placeholders import Anything, OneOf
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import AttrQuality, DevFailed, DeviceProxy, DevState, EventType

from ska_low_mccs_spshw.tile import (
    MccsTile,
    MockTpm,
    TileComponentManager,
    TileData,
    TileSimulator,
)
from tests.harness import SpsTangoTestHarness, SpsTangoTestHarnessContext
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
        "admin_mode",
        "health_state",
        "state",
        "communication_state",
        "tile_programming_state",
        "lrc_command",
        "adc_power",
        "pps_present",
        "track_lrc_command",
        timeout=15.0,
    )


@pytest.fixture(name="test_context")
def test_context_fixture(
    tile_id: int,
    patched_tile_device_class: type[MccsTile],
    mock_subrack_device_proxy: unittest.mock.Mock,
) -> Iterator[SpsTangoTestHarnessContext]:
    """
    Return a test context in which a tile Tango device is running.

    :param tile_id: the ID of the tile under test
    :param patched_tile_device_class: a subclass of MccsTile that has
        been patched with extra commands that mock system under control
        behaviours.
    :param mock_subrack_device_proxy: a mock proxy to the subrack Tango
        device.

    :yields: a test context.
    """
    harness = SpsTangoTestHarness()
    harness.add_mock_subrack_device(1, mock_subrack_device_proxy)
    harness.add_tile_device(
        tile_id,
        device_class=patched_tile_device_class,
    )
    with harness as context:
        yield context


@pytest.fixture(name="tile_device")
def tile_device_fixture(
    test_context: SpsTangoTestHarnessContext,
    tile_id: int,
) -> DeviceProxy:
    """
    Fixture that returns the tile Tango device under test.

    :param test_context: a test context in which the tile
        Tango device under test is running.
    :param tile_id: ID of the tile.

    :yield: the tile Tango device under test.
    """
    yield test_context.get_tile_device(tile_id)


@pytest.fixture(name="off_tile_device")
def off_tile_device_fixture(
    tile_device: DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> DeviceProxy:
    """
    Fixture that returns a DeviceProxy to a off tile.

    :param tile_device: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.

    :yield: a 'DeviceProxy' to the tile.
    """
    assert tile_device.adminMode == AdminMode.OFFLINE
    subscription_id = tile_device.subscribe_event(
        "state",
        EventType.CHANGE_EVENT,
        change_event_callbacks["state"],
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    assert tile_device.state() == DevState.DISABLE

    tile_device.adminMode = AdminMode.ONLINE
    assert tile_device.adminMode == AdminMode.ONLINE

    change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
    change_event_callbacks["state"].assert_change_event(DevState.OFF)
    tile_device.unsubscribe_event(subscription_id)
    yield tile_device


@pytest.fixture(name="on_tile_device")
def on_tile_device_fixture(
    tile_device: DeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> DeviceProxy:
    """
    Fixture that returns a DeviceProxy to a on tile.

    :param tile_device: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.

    :yield: a 'DeviceProxy' to the tile.
    """
    assert tile_device.adminMode == AdminMode.OFFLINE
    subscription_ids: list[int] = []
    subscription_ids.append(
        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
    )
    change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
    subscription_ids.append(
        tile_device.subscribe_event(
            "tileProgrammingState",
            EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
    )
    change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")
    tile_device.adminMode = AdminMode.ONLINE

    change_event_callbacks["state"].assert_change_event(
        OneOf(DevState.OFF, DevState.ON), lookahead=2, consume_nonmatches=True
    )
    change_event_callbacks["tile_programming_state"].assert_change_event("Off")

    tile_device.on()
    tile_device.MockTpmOn()

    change_event_callbacks["tile_programming_state"].assert_change_event(
        "NotProgrammed"
    )
    change_event_callbacks["tile_programming_state"].assert_change_event(
        "Initialised", lookahead=2, consume_nonmatches=True
    )

    change_event_callbacks["state"].assert_change_event(DevState.ON)

    assert tile_device.tileProgrammingState == "Initialised"
    for subscription_id in subscription_ids:
        tile_device.unsubscribe_event(subscription_id)
    wait_for_completed_command_to_clear_from_queue(tile_device)
    yield tile_device


def turn_tile_on(
    tile_device: MccsDeviceProxy,
    change_event_callbacks: MockTangoEventCallbackGroup,
) -> DeviceProxy:
    """
    Test TPM on sequence.

    :param tile_device: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.

    :returns: a 'DeviceProxy' to the tile.
    """
    subscription_ids: list[int] = []
    subscription_ids.append(
        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
    )
    change_event_callbacks["state"].assert_change_event(DevState.OFF)

    subscription_ids.append(
        tile_device.subscribe_event(
            "tileProgrammingState",
            EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
    )
    change_event_callbacks["tile_programming_state"].assert_change_event("Off")

    tile_device.on()
    tile_device.MockTpmOn()

    change_event_callbacks["tile_programming_state"].assert_change_event(
        "NotProgrammed", lookahead=2, consume_nonmatches=True
    )
    change_event_callbacks["tile_programming_state"].assert_change_event(
        "Initialised", lookahead=2, consume_nonmatches=True
    )

    change_event_callbacks["state"].assert_change_event(DevState.ON)

    assert tile_device.tileProgrammingState == "Initialised"
    for subscription_id in subscription_ids:
        tile_device.unsubscribe_event(subscription_id)
    return tile_device


# pylint: disable=too-many-lines
class TestMccsTile:
    """
    Test class for MccsTile tests.

    The Tile device represents the TANGO interface to a Tile (TPM) unit.
    """

    def test_state_with_adminmode(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test TANGO state gets updated as expected.

        The ``MccsTile`` device should undergo state changes when its adminMode changes:
        - when adminMode is ``OFFLINE`` the device should become ``DISABLED``
        - when adminMode is ``ONLINE`` the device should attempt to work out the
        state of the component under control and transition.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)

        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)
        change_event_callbacks["state"].assert_not_called()

        # Check when adminMode OFFLINE state transitions to DISABLE
        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        # Check when adminMode ONLINE state transitions to state of underlying device
        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)

        # Check when adminMode OFFLINE state transitions to DISABLE (again)
        tile_device.adminMode = AdminMode.OFFLINE
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        # Check when adminMode ONLINE state transitions to state of underlying device
        tile_device.adminMode = AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)

    @pytest.mark.parametrize(
        "config_in, expected_config",
        [
            pytest.param(
                {
                    "fixed_delays": [i + 1 for i in range(32)],
                    "antenna_ids": [i + 1 for i in range(16)],
                },
                {
                    "fixed_delays": [
                        1.25,
                        2.5,
                        2.5,
                        3.75,
                        5.0,
                        6.25,
                        7.5,
                        7.5,
                        8.75,
                        10.0,
                        11.25,
                        12.5,
                        12.5,
                        13.75,
                        15.0,
                        16.25,
                        17.5,
                        17.5,
                        18.75,
                        20.0,
                        21.25,
                        22.5,
                        22.5,
                        23.75,
                        25.0,
                        26.25,
                        27.5,
                        27.5,
                        28.75,
                        30.0,
                        31.25,
                        32.5,
                    ],
                    "antenna_ids": [i + 1 for i in range(16)],
                },
                id="valid config is entered correctly",
            ),
            pytest.param(
                {
                    "fixed_delays": [i + 1 for i in range(32)],
                },
                {
                    "fixed_delays": [
                        1.25,
                        2.5,
                        2.5,
                        3.75,
                        5.0,
                        6.25,
                        7.5,
                        7.5,
                        8.75,
                        10.0,
                        11.25,
                        12.5,
                        12.5,
                        13.75,
                        15.0,
                        16.25,
                        17.5,
                        17.5,
                        18.75,
                        20.0,
                        21.25,
                        22.5,
                        22.5,
                        23.75,
                        25.0,
                        26.25,
                        27.5,
                        27.5,
                        28.75,
                        30.0,
                        31.25,
                        32.5,
                    ],
                    "antenna_ids": [],
                },
                id="missing config data is valid",
            ),
            pytest.param(
                {
                    "fixed_delays_wrong_name": [i + 1 for i in range(32)],
                },
                {
                    "fixed_delays": [],
                    "antenna_ids": [],
                },
                id="invalid named configs are skipped",
            ),
            pytest.param(
                {},
                {
                    "fixed_delays": [],
                    "antenna_ids": [],
                },
                id="invalid types dont apply",
            ),
        ],
    )
    def test_Configure(
        self: TestMccsTile,
        on_tile_device: MccsDeviceProxy,
        config_in: dict,
        expected_config: dict,
    ) -> None:
        """
        Test for Configure.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param config_in: configuration of the device
        :param expected_config: the expected output configuration
        """
        init_value = on_tile_device.staticTimeDelays
        # there is a static delay applied to each ADC channel.
        assert len(init_value) == 32

        print(f"the init_value are: {init_value}")
        on_tile_device.Configure(json.dumps(config_in))

        assert list(on_tile_device.antennaIds) == expected_config["antenna_ids"]

        value = expected_config["fixed_delays"]
        write_value = np.array(value)
        init_value = np.array(init_value)
        print(f"the fdelays are: {on_tile_device.staticTimeDelays}")
        if value:
            assert (on_tile_device.staticTimeDelays == write_value).all()
        else:
            assert (on_tile_device.staticTimeDelays == init_value).all()

    def test_healthState(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        tile_component_manager: unittest.mock.Mock,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for healthState.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param tile_component_manager: A component manager.
            (Using a TileSimulator)
        """
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.subscribe_event(
            "healthState",
            EventType.CHANGE_EVENT,
            change_event_callbacks["health_state"],
        )

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )

        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        change_event_callbacks["health_state"].assert_change_event(HealthState.UNKNOWN)
        assert tile_device.healthState == HealthState.UNKNOWN

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)

        tile_component_manager._update_communication_state(
            CommunicationStatus.ESTABLISHED
        )
        tile_component_manager._update_component_state(
            fault=False,
            power=PowerState.ON,
            tile_health_structure=TileData.get_tile_defaults(),
        )

        change_event_callbacks["state"].assert_change_event(DevState.ON)
        change_event_callbacks["health_state"].assert_change_event(HealthState.OK)

    def test_adcPower(
        self: TestMccsTile,
        on_tile_device: MccsDeviceProxy,
        tile_component_manager: unittest.mock.Mock,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for adcPower.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param tile_component_manager: A component manager.
            (Using a TileSimulator)
        """
        on_tile_device.subscribe_event(
            "adcPower",
            EventType.CHANGE_EVENT,
            change_event_callbacks["adc_power"],
        )

        tile_component_manager._update_communication_state(
            CommunicationStatus.ESTABLISHED
        )
        tile_component_manager._adc_rms = list(range(32))
        tile_component_manager._update_component_state(
            fault=False,
            power=PowerState.ON,
            tile_health_structure=TileData.get_tile_defaults(),
            adc_rms=list(range(32)),
        )
        change_event_callbacks["adc_power"].assert_change_event(list(range(32)))

    def test_ppsPresent(
        self: TestMccsTile,
        on_tile_device: MccsDeviceProxy,
        tile_component_manager: unittest.mock.Mock,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test alarm is raised when pps is disconnected.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param tile_component_manager: A component manager.
            (Using a TileSimulator)
        """
        tile_component_manager._request_provider.get_request = unittest.mock.Mock(
            return_value=("HEALTH_STATUS", None)
        )
        time.sleep(2)
        on_tile_device.subscribe_event(
            "ppsPresent",
            EventType.CHANGE_EVENT,
            change_event_callbacks["pps_present"],
        )
        change_event_callbacks["pps_present"].assert_change_event(True)
        assert (
            on_tile_device.read_attribute("ppspresent").quality
            == AttrQuality.ATTR_VALID
        )
        tile_component_manager._update_communication_state(
            CommunicationStatus.ESTABLISHED
        )

        # Simulate disconnection the PPS.
        tile_monitoring_defaults = copy.deepcopy(TileData.get_tile_defaults())
        tile_monitoring_defaults["timing"]["pps"]["status"] = False

        tile_component_manager._update_component_state(
            tile_health_structure=tile_monitoring_defaults,
        )
        change_event_callbacks["pps_present"].assert_change_event(False)
        assert (
            on_tile_device.read_attribute("ppspresent").quality
            == AttrQuality.ATTR_ALARM
        )
        assert on_tile_device.state() == DevState.ALARM

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        ("attribute", "initial_value", "write_value"),
        [
            ("logicalTileId", 1, 7),
            ("stationId", 1, 5),
            ("fpgasUnixTime", pytest.approx(TileSimulator.FPGAS_TIME), None),
            (
                "currentTileBeamformerFrame",
                TileSimulator.CURRENT_TILE_BEAMFORMER_FRAME,
                None,
            ),
            ("currentFrame", 0, None),
            ("ppsDelay", 12, None),
            # TODO Tests fail as np.ndarray is returned.
            (
                "channeliserRounding",
                TileSimulator.CHANNELISER_TRUNCATION,
                [2] * 512,
            ),
            ("cspRounding", TileSimulator.CSP_ROUNDING, [3] * 384),
        ],
    )
    def test_component_attribute(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        attribute: str,
        initial_value: Any,
        mock_subrack_device_proxy: unittest.mock.Mock,
        write_value: Any,
    ) -> None:
        """
        Test device attributes that map through to the component.

        Thus require the component to be connected and turned on before
        a read / write can be effected.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param attribute: name of the attribute under test
        :param initial_value: expected initial value of the attribute
        :param mock_subrack_device_proxy: a mock proxy to the subrack Tango
            device.
        :param write_value: value to be written as part of the test.
        """
        assert tile_device.adminMode == AdminMode.OFFLINE
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=PowerState.ON)
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = getattr(tile_device, attribute)

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        tile_device.subscribe_event(
            "tileprogrammingstate",
            EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.ON)
        tile_device.initialise()
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Initialised", lookahead=4
        )
        if isinstance(initial_value, list):
            initial_value = np.array(initial_value)
            assert (getattr(tile_device, attribute) == initial_value).all()
        else:
            assert getattr(tile_device, attribute) == initial_value

        if write_value is not None:
            tile_device.write_attribute(attribute, write_value)
            time.sleep(3)
            if isinstance(write_value, list):
                write_value = np.array(write_value)
                assert (getattr(tile_device, attribute) == write_value).all()
            else:
                assert getattr(tile_device, attribute) == write_value

    # pylint: disable=too-many-arguments
    @pytest.mark.parametrize(
        ("attribute", "initial_value", "write_value"),
        [
            (
                "voltageMon",
                TileSimulator.TILE_MONITORING_POINTS["voltages"]["MON_5V0"],
                None,
            ),
            (
                "boardTemperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["board"],
                None,
            ),
            (
                "fpga1Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA0"],
                None,
            ),
            (
                "fpga2Temperature",
                TileSimulator.TILE_MONITORING_POINTS["temperatures"]["FPGA1"],
                None,
            ),
            (
                "adcPower",
                # pytest.approx(tuple(float(i) for i in range(32))),
                list(float(i) for i in range(32)),
                None,
            ),
            ("preaduLevels", TileSimulator.PREADU_LEVELS, [5] * 32),
            ("staticTimeDelays", TileSimulator.STATIC_DELAYS, [12.5] * 32),
            ("pllLocked", True, None),
        ],
    )
    def test_component_cached_attribute(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        attribute: str,
        initial_value: Any,
        mock_subrack_device_proxy: unittest.mock.Mock,
        write_value: Any,
    ) -> None:
        """
        Test device attributes that map through to the component.

        Thus require the component to be connected and turned on before
        a read / write can be effected.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param attribute: name of the attribute under test
        :param initial_value: expected initial value of the attribute
        :param mock_subrack_device_proxy: a mock proxy to the subrack Tango
            device.
        :param write_value: value to be written as part of the test.
        """
        assert tile_device.adminMode == AdminMode.OFFLINE
        mock_subrack_device_proxy.configure_mock(tpm1PowerState=PowerState.ON)
        with pytest.raises(
            DevFailed,
            match=f"Read value for attribute {attribute} has not been updated",
        ):
            _ = getattr(tile_device, attribute)

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        tile_device.subscribe_event(
            "tileprogrammingstate",
            EventType.CHANGE_EVENT,
            change_event_callbacks["tile_programming_state"],
        )
        change_event_callbacks["tile_programming_state"].assert_change_event("Unknown")
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.ON)
        tile_device.initialise()
        change_event_callbacks["tile_programming_state"].assert_change_event(
            "Initialised", lookahead=4
        )
        time.sleep(3)
        if isinstance(initial_value, list):
            initial_value = np.array(initial_value)
            assert (getattr(tile_device, attribute) == initial_value).all()
        else:
            assert getattr(tile_device, attribute) == initial_value

        if write_value is not None:
            tile_device.write_attribute(attribute, write_value)
            time.sleep(3)
            if isinstance(write_value, list):
                write_value = np.array(write_value)
                assert (getattr(tile_device, attribute) == write_value).all()
            else:
                assert getattr(tile_device, attribute) == write_value

    def test_antennaIds(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for the antennaIds attribute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        assert tuple(tile_device.antennaIds) == tuple()
        new_ids = tuple(range(8))
        tile_device.antennaIds = new_ids
        assert tuple(tile_device.antennaIds) == new_ids

    @pytest.mark.parametrize(
        ("expected_init_params", "new_params"),
        [
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS,
                {
                    "temperatures": {"board": {"max": 70}},
                    "timing": {"clocks": {"FPGA0": {"JESD": False}}},
                },
                id="Check temperature and timing values and check new values",
            ),
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS,
                {
                    "currents": {"FE0_mVA": {"max": 25}},
                    "io": {
                        "jesd_interface": {
                            "lane_error_count": {"FPGA0": {"Core0": {"lane3": 2}}}
                        }
                    },
                },
                id="Change current and io values and check new values",
            ),
            pytest.param(
                TileData.MIN_MAX_MONITORING_POINTS,
                {
                    "alarms": {"I2C_access_alm": 1},
                    "adcs": {"pll_status": {"ADC0": (False, True)}},
                    "dsp": {"station_beamf": {"ddr_parity_error_count": {"FPGA1": 1}}},
                },
                id="Change alarm, adc and dsp values and check new values",
            ),
        ],
    )
    def test_healthParams(
        self: TestMccsTile,
        tile_device: MccsDeviceProxy,
        expected_init_params: dict[str, Any],
        new_params: dict[str, Any],
    ) -> None:
        """
        Test for healthParams attributes.

        :param tile_device: the Tile Tango device under test.
        :param expected_init_params: the initial values which the health model is
            expected to have initially
        :param new_params: the new health rule params to pass to the health model
        """

        def _merge_dicts(
            dict_a: dict[str, Any], dict_b: dict[str, Any]
        ) -> dict[str, Any]:
            output = copy.deepcopy(dict_a)
            for key in dict_b:
                if isinstance(dict_b[key], dict):
                    output[key] = _merge_dicts(dict_a[key], dict_b[key])
                else:
                    output[key] = dict_b[key]
            return output

        assert tile_device.healthModelParams == json.dumps(expected_init_params)
        new_params_json = json.dumps(new_params)
        tile_device.healthModelParams = new_params_json  # type: ignore[assignment]
        expected_result = copy.deepcopy(expected_init_params)
        expected_result = _merge_dicts(expected_result, new_params)
        assert tile_device.healthModelParams == json.dumps(expected_result)


class TestMccsTileCommands:
    """Tests of MccsTile device commands."""

    @pytest.mark.parametrize(
        ("device_command", "arg"),
        [
            (
                "LoadPointingDelays",
                [3] + [1e-6, 2e-8] * 16,
            ),  # 2 * antennas_per_tile + 1
            (
                "ConfigureIntegratedChannelData",
                json.dumps(
                    {
                        "integration_time": 6.284,
                        "first_channel": 0,
                        "last_channel": 511,
                    }
                ),
            ),
            (
                "ConfigureIntegratedBeamData",
                json.dumps(
                    {
                        "integration_time": 3.142,
                        "first_channel": 0,
                        "last_channel": 191,
                    }
                ),
            ),
            (
                "SetLmcIntegratedDownload",
                json.dumps(
                    {
                        "mode": "1G",
                        "channel_payload_length": 4,
                        "beam_payload_length": 6,
                        "destination_ip": "10.0.1.23",
                    }
                ),
            ),
            ("ApplyCalibration", ""),
            ("ApplyPointingDelays", ""),
            ("StopIntegratedData", None),
        ],
    )
    def test_command_can_execute(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        device_command: str,
        arg: Any,
    ) -> None:
        """
        A very weak test for commands that are not implemented yet.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param device_command: the name of the device command under test
        :param arg: argument to the command (optional)
        """
        assert tile_device.adminMode == AdminMode.OFFLINE
        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )

        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        args = [] if arg is None else [arg]
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = getattr(tile_device, device_command)(*args)

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE

        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)
        tile_device.MockTpmOn()
        change_event_callbacks["state"].assert_change_event(DevState.ON)

    @pytest.mark.parametrize(
        ("command_name", "command_args"),
        [
            ("Initialise", None),
            ("DownloadFirmware", "tests/data/Vivado_test_firmware_bitfile.bit"),
        ],
    )
    def test_long_running_commands(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
        command_name: str,
        command_args: Optional[str],
    ) -> None:
        """
        Test that LongRunningCommand can execute.

        Here we are testing the 'Initialise' and 'DownloadFirmware' command the start
        acquisition is tested in 'test_StartAcquisition'

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param command_name: the name of the command to test
        :param command_args: the arguments to pass to the command under
            test.
        """
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        tile_device.subscribe_event(
            "longrunningcommandstatus",
            EventType.CHANGE_EVENT,
            change_event_callbacks["lrc_command"],
        )
        change_event_callbacks["lrc_command"].assert_change_event(Anything)

        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE

        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)

        change_event_callbacks["state"].assert_change_event(DevState.OFF)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            [[task_status], [command_id]] = getattr(tile_device, command_name)(
                command_args
            )

        change_event_callbacks["lrc_command"].assert_change_event(Anything)
        wait_for_completed_command_to_clear_from_queue(tile_device)
        tile_device.MockTpmOn()
        change_event_callbacks["state"].assert_change_event(DevState.ON)

        [[task_status], [command_id]] = getattr(tile_device, command_name)(command_args)

        assert task_status == TaskStatus.IN_PROGRESS
        assert command_name in command_id.split("_")[-1]

        change_event_callbacks["lrc_command"].assert_change_event(
            (command_id, "QUEUED")
        )
        change_event_callbacks["lrc_command"].assert_change_event(
            (command_id, "IN_PROGRESS")
        )
        change_event_callbacks["lrc_command"].assert_change_event(
            (command_id, "COMPLETED")
        )

    def test_StartAcquisition(
        self: TestMccsTileCommands,
        tile_device: DeviceProxy,
        tile_component_manager: TileComponentManager,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test that start acquisition can execute.

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        :param tile_component_manager: the tile_component_manager fixture.
        """
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        tile_device.subscribe_event(
            "longrunningcommandstatus",
            EventType.CHANGE_EVENT,
            change_event_callbacks["lrc_command"],
        )
        change_event_callbacks["lrc_command"].assert_change_event(Anything)

        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        assert tile_device.state() == DevState.DISABLE

        tile_device.adminMode = AdminMode.ONLINE
        assert tile_device.adminMode == AdminMode.ONLINE

        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)

        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            [[task_status], [command_id]] = tile_device.StartAcquisition(
                json.dumps({"delay": 5})
            )

        change_event_callbacks["lrc_command"].assert_change_event(Anything)
        wait_for_completed_command_to_clear_from_queue(tile_device)

        tile_device.MockTpmOn()

        change_event_callbacks["state"].assert_change_event(DevState.ON)

        [[task_status], [command_id]] = tile_device.StartAcquisition(
            json.dumps({"delay": 5})
        )

        change_event_callbacks["lrc_command"].assert_change_event(
            (command_id, "QUEUED")
        )
        # This will never be picked up since we need to be Initialised or
        # Synchronised to execute. This is by default 60 seconds, but this test speeds
        # that up.
        request_provider = tile_component_manager._request_provider
        if request_provider:
            request_provider.command_wipe_time["start_acquisition"] = time.time() + 5

        change_event_callbacks["lrc_command"].assert_change_event(
            (command_id, "ABORTED")
        )

        wait_for_completed_command_to_clear_from_queue(tile_device)
        execute_lrc_to_complettion(
            change_event_callbacks, tile_device, "Initialise", None
        )
        wait_for_completed_command_to_clear_from_queue(tile_device)

        execute_lrc_to_complettion(
            change_event_callbacks,
            tile_device,
            "StartAcquisition",
            json.dumps({"delay": 5}),
        )

    def test_GetFirmwareAvailable(
        self: TestMccsTileCommands,
        off_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test if firmware available.

        Test for:
        * GetFirmwareAvailable command
        * firmwareName attribute
        * firmwareVersion attribute

        :param off_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        # At this point, the component should be unconnected, as not turned on
        with pytest.raises(
            DevFailed,
            match="Communication with component is not established",
        ):
            _ = off_tile_device.GetFirmwareAvailable()
        # self.turn_tile_on(off_tile_device, change_event_callbacks)
        # off_tile_device.MockTpmOn()
        # change_event_callbacks["state"].assert_change_event(DevState.ON)
        on_tile_device = turn_tile_on(off_tile_device, change_event_callbacks)

        firmware_available_str = on_tile_device.GetFirmwareAvailable()
        firmware_available = json.loads(firmware_available_str)
        assert firmware_available == TileSimulator.FIRMWARE_LIST

        firmware_name = on_tile_device.firmwareName
        assert firmware_name == TileSimulator.FIRMWARE_NAME

        major = firmware_available[0]["major"]
        minor = firmware_available[0]["minor"]
        build = firmware_available[0]["build"]

        assert on_tile_device.firmwareVersion == f"Ver.{major}.{minor} build {build}:"

    def test_MissingDownloadFirmwareFile(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for a missing firmware download.

        Also functions as the test for the
        isProgrammed and the firmwareName properties.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        invalid_bitfile_path = "this/folder/and/file/doesnt/exist.bit"
        existing_firmware_name = on_tile_device.firmwareName
        [[result_code], [message]] = on_tile_device.DownloadFirmware(
            invalid_bitfile_path
        )
        assert result_code == ResultCode.FAILED
        assert "DownloadFirmware" not in message.split("_")[-1]
        assert on_tile_device.firmwareName == existing_firmware_name

    def test_GetRegisterList(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for GetRegisterList.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        assert on_tile_device.GetRegisterList() == list(MockTpm._register_map.keys())

    def test_ReadRegister(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for ReadRegister.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        register_name: str = "fpga2.test_generator.delay_0"
        values = on_tile_device.ReadRegister(register_name)
        assert list(values) == [MockTpm._register_map[register_name]]

    def test_WriteRegister(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for WriteRegister.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        arg = {
            "register_name": "test-reg1",
            "values": [0, 1, 2, 3],
        }
        json_arg = json.dumps(arg)
        [[result_code], [message]] = on_tile_device.WriteRegister(json_arg)
        assert result_code == ResultCode.OK
        assert "WriteRegister" in message.split("_")[-1]

        for exclude_key in ["register_name", "values"]:
            bad_arg = {key: value for key, value in arg.items() if key != exclude_key}
            bad_json_arg = json.dumps(bad_arg)
            with pytest.raises(
                DevFailed,
                match=f"'{exclude_key}' is a required property",
            ):
                _ = on_tile_device.WriteRegister(bad_json_arg)

    def test_ReadAddress(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for ReadAddress.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        address = 0xF
        nvalues = 10
        expected = (0,) * nvalues
        assert tuple(on_tile_device.ReadAddress([address, nvalues])) == expected

        expected = (0,)
        assert on_tile_device.ReadAddress([address]) == expected

    def test_WriteAddress(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for WriteAddress.

        This is a very weak test but the
        :py:class:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager`'s
        :py:meth:`~ska_low_mccs.tile.tile_hardware.TileHardwareManager.write_address`
        method is well tested.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        [[result_code], [message]] = on_tile_device.WriteAddress([20, 1, 2, 3])
        assert result_code == ResultCode.OK
        assert "WriteAddress" in message.split("_")[-1]

    def test_Configure40GCore(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for.

        * Configure40GCore command
        * fortyGBDestinationIps attribute
        * fortyGBDestinationPorts attribute

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        config_1 = {
            "core_id": 0,
            "arp_table_entry": 0,
            "source_mac": "10:fe:ed:08:0a:58",
            "source_ip": "10.0.99.3",
            "source_port": 4000,
            "destination_ip": "10.0.98.3",
            "destination_port": 5000,
        }
        on_tile_device.Configure40GCore(json.dumps(config_1))

        config_2 = {
            "core_id": 1,
            "arp_table_entry": 1,
            "source_mac": "10:fe:ed:08:0a:56",
            "source_ip": "10.0.99.4",
            "source_port": 4001,
            "destination_ip": "10.0.98.4",
            "destination_port": 5001,
        }
        on_tile_device.Configure40GCore(json.dumps(config_2))

        assert tuple(on_tile_device.fortyGbDestinationIps) == (
            "10.0.98.3",
            "10.0.98.4",
        )
        assert tuple(on_tile_device.fortyGbDestinationPorts) == (5000, 5001)

        arg = {
            "core_id": 0,
            "arp_table_entry": 0,
        }
        json_arg = json.dumps(arg)
        result_str = on_tile_device.Get40GCoreConfiguration(json_arg)
        result = json.loads(result_str)
        assert result["core_id"] == config_1.pop("core_id")

        arg = {
            "core_id": 3,
            "arp_table_entry": 0,
        }
        json_arg = json.dumps(arg)

        with pytest.raises(
            DevFailed, match="Invalid core id or arp table id specified"
        ):
            _ = on_tile_device.Get40GCoreConfiguration(json_arg)

        arg2 = {"mode": "10G", "payload_length": 102, "destination_ip": "10.0.1.23"}
        json_arg = json.dumps(arg2)
        on_tile_device.SetLmcDownload(json_arg)

    def test_LoadCalibrationCoefficients(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for LoadCalibrationCoefficients.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        antenna = float(2)
        complex_coefficients = [
            [
                complex(3.4, 1.2),
                complex(2.3, 4.1),
                complex(4.6, 8.2),
                complex(6.8, 2.4),
            ]
        ] * 5
        inp = list(itertools.chain.from_iterable(complex_coefficients))
        out = [[v.real, v.imag] for v in inp]
        coefficients = [antenna] + list(itertools.chain.from_iterable(out))

        # check that it can execute without exception
        _ = on_tile_device.LoadCalibrationCoefficients(coefficients)

        with pytest.raises(DevFailed, match="ValueError"):
            _ = on_tile_device.LoadCalibrationCoefficients(coefficients[0:8])

        with pytest.raises(DevFailed, match="ValueError"):
            _ = on_tile_device.LoadCalibrationCoefficients(coefficients[0:16])

    @pytest.mark.parametrize("start_time", (None,))
    @pytest.mark.parametrize("duration", (None, -1))
    def test_start_and_stop_beamformer(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        start_time: Optional[int],
        duration: Optional[int],
    ) -> None:
        """
        Test for.

        * StartBeamformer command
        * StopBeamformer command
        * isBeamformerRunning attribute

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param start_time: time to state the beamformer
        :param duration: duration of time that the beamformer should run
        """
        assert not on_tile_device.isBeamformerRunning
        args = {"start_time": start_time, "duration": duration}
        on_tile_device.StartBeamformer(json.dumps(args))
        assert on_tile_device.isBeamformerRunning
        on_tile_device.StopBeamformer()
        assert not on_tile_device.isBeamformerRunning

    def test_configure_beamformer(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test for.

        ConfigureStationBeamformer
        SetBeamFormerRegions
        beamformerTable attribute

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        on_tile_device.ConfigureStationBeamformer(
            json.dumps(
                {
                    "start_channel": 2,
                    "n_channels": 8,
                    "is_first": True,
                    "is_last": False,
                }
            )
        )
        time.sleep(3)
        table = list(on_tile_device.beamformerTable)
        expected = [2, 0, 0, 0, 0, 0, 0]  # + [0, 0, 0, 0, 0, 0, 0] * 47
        assert table == expected

        on_tile_device.SetBeamFormerRegions([2, 8, 5, 3, 8, 1, 1, 101])
        time.sleep(3)
        table = list(on_tile_device.beamformerTable)
        expected = [2, 5, 3, 8, 1, 1, 101]  # + [0, 0, 0, 0, 0, 0, 0] * 47
        assert table == expected

    def test_send_data_samples(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for various flavors of SendDataSamples.

        Also tests:
        CheckPendingDataRequests
        StopDataTransmission

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        wait_for_completed_command_to_clear_from_queue(on_tile_device)

        execute_lrc_to_complettion(
            change_event_callbacks,
            on_tile_device,
            "StartAcquisition",
            json.dumps({"delay": 5}),
        )
        args = [
            {"data_type": "raw", "sync": True, "seconds": 6.7},
            {
                "data_type": "channel",
                "n_samples": 4,
                "first_channel": 7,
                "last_channel": 234,
            },
            {"data_type": "beam", "seconds": 0.5},
            {
                "data_type": "narrowband",
                "frequency": 150e6,
                "round_bits": 6,
                "n_samples": 128,
                "seconds": 0.5,
            },
        ]
        for arg in args:
            time.sleep(0.1)
            json_arg = json.dumps(arg)
            [[result_code], [message]] = on_tile_device.SendDataSamples(json_arg)
            assert result_code == ResultCode.OK

        assert not on_tile_device.pendingDataRequests
        json_arg = json.dumps(
            {"data_type": "channel_continuous", "channel_id": 2, "n_samples": 4}
        )
        print("adojsaodijasodij")
        [[result_code], [message]] = on_tile_device.SendDataSamples(json_arg)
        assert result_code == ResultCode.OK
        time.sleep(0.2)
        assert on_tile_device.pendingDataRequests
        on_tile_device.StopDataTransmission()
        time.sleep(0.1)
        assert not on_tile_device.pendingDataRequests

        invalid_channel_range_args = [
            {"data_type": "channel", "first_channel": 0, "last_channel": 512},
            {"data_type": "channel", "first_channel": -1, "last_channel": 511},
            {"data_type": "channel", "first_channel": 511, "last_channel": 0},
        ]
        error_matches = [
            "512 is greater than the maximum of 511",
            "-1 is less than the minimum of 0",
            r"last channel \(0\) cannot be less than first channel \(511\)",
        ]
        for arg, error_match in zip(invalid_channel_range_args, error_matches):
            time.sleep(0.1)
            json_arg = json.dumps(arg)
            with pytest.raises(DevFailed, match=error_match):
                on_tile_device.SendDataSamples(json_arg)

    def test_configure_test_generator(
        self: TestMccsTileCommands,
        tile_device: MccsDeviceProxy,
        change_event_callbacks: MockTangoEventCallbackGroup,
    ) -> None:
        """
        Test for various flavors of TestGenerator signals.

        Also tests:
        TestGeneratorActive

        :param tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        :param change_event_callbacks: dictionary of Tango change event
            callbacks with asynchrony support.
        """
        tile_device.subscribe_event(
            "state",
            EventType.CHANGE_EVENT,
            change_event_callbacks["state"],
        )
        change_event_callbacks["state"].assert_change_event(DevState.DISABLE)
        assert tile_device.adminMode == AdminMode.OFFLINE

        tile_device.adminMode = AdminMode.MAINTENANCE
        assert tile_device.adminMode == AdminMode.MAINTENANCE
        change_event_callbacks["state"].assert_change_event(DevState.UNKNOWN)
        change_event_callbacks["state"].assert_change_event(DevState.OFF)
        tile_device.MockTpmOn()
        change_event_callbacks["state"].assert_change_event(DevState.ON)
        args = [
            {
                "tone_frequency": 100e6,
                "tone_amplitude": 0.5,
                "tone_2_frequency": 100e6,
                "tone_2_amplitude": 0.5,
                "noise_amplitude": 0.3,
                "pulse_frequency": 5,
                "pulse_amplitude": 0.2,
                "adc_channels": [1, 2, 3, 14],
            },
            {
                "tone_frequency": 100e6,
                "tone_amplitude": 0.5,
            },
            {"noise_amplitude": 1.0},
        ]
        for arg in args:
            tile_device.loggingLevel = 5
            tile_device.ConfigureTestGenerator(json.dumps(arg))
            assert tile_device.testGeneratorActive is True
            tile_device.ConfigureTestGenerator("{}")
            assert tile_device.testGeneratorActive is False
            tile_device.loggingLevel = 3
        with pytest.raises(DevFailed, match="8 is greater than the maximum of 7"):
            tile_device.ConfigureTestGenerator(json.dumps({"pulse_frequency": 8}))

    def test_get_arp_table(
        self: TestMccsTileCommands,
        on_tile_device: MccsDeviceProxy,
    ) -> None:
        """
        Test that GetArpTable returns a result.

        :param on_tile_device: fixture that provides a
            :py:class:`tango.DeviceProxy` to the device under test, in a
            :py:class:`tango.test_context.DeviceTestContext`.
        """
        result = on_tile_device.GetArpTable()
        assert json.loads(result) == {"0": [0, 1], "1": [1]}
