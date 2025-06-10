# -*- coding: utf-8 -*
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
This module contains pytest fixtures other test setups.

These are common to all ska-low-mccs tests: unit, integration and
functional (BDD).
"""
from __future__ import annotations

import enum
import json
import time
from datetime import datetime
from typing import Any

import numpy as np
import pytest
import tango
from ska_control_model import AdminMode, ResultCode
from ska_tango_testing.mock.placeholders import Anything
from ska_tango_testing.mock.tango import MockTangoEventCallbackGroup
from tango import EventType


class TpmStatus(enum.IntEnum):
    """
    Enumerated type for tile status.

    Used in initialisation to know what long running commands have been
    issued
    """

    UNKNOWN = 0
    """The status is not known."""

    OFF = 1
    """The TPM is not powered."""

    UNCONNECTED = 2
    """The TPM is not connected."""

    UNPROGRAMMED = 3
    """The TPM is powered on but FPGAS are not programmed."""

    PROGRAMMED = 4
    """The TPM is powered on and FPGAS are programmed."""

    INITIALISED = 5
    """Initialise command has been issued."""

    SYNCHRONISED = 6
    """Time has been synchronised with UTC, timestamp is valid."""

    # TODO: More status values to come, for complete configuration in station

    def pretty_name(self: TpmStatus) -> str:
        """
        Return string representation.

        :return: String representation in camelcase
        """
        status_names = {
            TpmStatus.UNKNOWN: "Unknown",
            TpmStatus.OFF: "Off",
            TpmStatus.UNCONNECTED: "Unconnected",
            TpmStatus.UNPROGRAMMED: "NotProgrammed",
            TpmStatus.PROGRAMMED: "Programmed",
            TpmStatus.INITIALISED: "Initialised",
            TpmStatus.SYNCHRONISED: "Synchronised",
        }
        return status_names[self]


RFC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def wait_for_completed_command_to_clear_from_queue(
    device_proxy: tango.DeviceProxy,
) -> None:
    """
    Wait for Long Running Commands to clear from queue.

    A completed command is expected to clear after 10 seconds.

    :param device_proxy: device proxy for use in the test.
    """
    # base class clears after 10 seconds
    count = 0
    timeout = 20

    while device_proxy.longRunningCommandsInQueue != ():
        time.sleep(0.5)
        count += 1
        if count == timeout:
            if device_proxy.longRunningCommandsInQueue != ():
                pytest.fail(
                    f"LRCs still in queue after {timeout} seconds: "
                    f"{device_proxy.dev_name()} : "
                    f"{device_proxy.longRunningCommandsInQueue}"
                )


def execute_lrc_to_completion(
    change_event_callbacks: MockTangoEventCallbackGroup,
    device_proxy: tango.DeviceProxy,
    command_name: str,
    command_arguments: Any,
) -> None:
    """
    Execute a LRC to completion.

    :param device_proxy: fixture that provides a
        :py:class:`tango.DeviceProxy` to the device under test, in a
        :py:class:`tango.test_context.DeviceTestContext`.
    :param change_event_callbacks: dictionary of Tango change event
        callbacks with asynchrony support.
    :param command_name: the name of the device command under test
    :param command_arguments: argument to the command (optional)
    """
    subscription_id = device_proxy.subscribe_event(
        "longrunningcommandstatus",
        EventType.CHANGE_EVENT,
        change_event_callbacks["track_lrc_command"],
    )
    change_event_callbacks["track_lrc_command"].assert_change_event(Anything)
    [[task_status], [command_id]] = getattr(device_proxy, command_name)(
        command_arguments
    )

    assert task_status == ResultCode.QUEUED
    assert command_name in command_id.split("_")[-1]
    change_event_callbacks["track_lrc_command"].assert_change_event(
        (command_id, "STAGING")
    )
    change_event_callbacks["track_lrc_command"].assert_change_event(
        (command_id, "QUEUED")
    )
    change_event_callbacks["track_lrc_command"].assert_change_event(
        (command_id, "IN_PROGRESS")
    )
    change_event_callbacks["track_lrc_command"].assert_change_event(
        (command_id, "COMPLETED")
    )
    device_proxy.unsubscribe_event(subscription_id)


def retry_communication(device_proxy: tango.Deviceproxy, timeout: int = 30) -> None:
    """
    Retry communication with the backend.

    NOTE: This is to be used for devices that do not know if the backend is available
    at the time of the call. For example the daq_handler backend gRPC server
    may not be ready when we try to start communicating.
    In this case we will retry connection.

    :param device_proxy: A 'tango.DeviceProxy' to the backend device.
    :param timeout: A max time in seconds before we give up trying
    """
    tick = 2
    if device_proxy.adminMode != AdminMode.ONLINE:
        terminate_time = time.time() + timeout
        while time.time() < terminate_time:
            try:
                device_proxy.adminMode = AdminMode.ONLINE
                break
            except tango.DevFailed:
                print(f"{device_proxy.dev_name()} failed to communicate with backend.")
                time.sleep(tick)
        assert device_proxy.adminMode == AdminMode.ONLINE
    else:
        print(f"Device {device_proxy.dev_name()} is already ONLINE nothing to do.")


class AttributeWaiter:  # pylint: disable=too-few-public-methods
    """A AttributeWaiter class."""

    def __init__(self: AttributeWaiter, timeout: float = 2.0) -> None:
        """
        Initialise a new AttributeWaiter with a timeout.

        :param timeout: the timeout to wait.
        """
        self._attr_callback = MockTangoEventCallbackGroup(
            "attr_callback", timeout=timeout
        )

    def wait_for_value(
        self: AttributeWaiter,
        device_proxy: tango.DeviceProxy,
        attr_name: str,
        attr_value: Any = None,
        lookahead: int = 1,
    ) -> None:
        """
        Wait for the value in alloted time.

        :param device_proxy: the device proxy
        :param attr_name: the name of the attribute
        :param attr_value: the value of the attribute
        :param lookahead: the lookahead.
        """
        subscription_id = device_proxy.subscribe_event(
            attr_name,
            EventType.CHANGE_EVENT,
            self._attr_callback["attr_callback"],
        )
        self._attr_callback["attr_callback"].assert_change_event(Anything)
        try:
            read_attr_value = getattr(device_proxy, attr_name)
            if isinstance(read_attr_value, np.ndarray):
                if not np.array_equal(read_attr_value, attr_value):
                    self._attr_callback["attr_callback"].assert_change_event(
                        attr_value or Anything,
                        lookahead=lookahead,
                        consume_nonmatches=True,
                    )
            elif read_attr_value != attr_value:
                self._attr_callback["attr_callback"].assert_change_event(
                    attr_value or Anything,
                    lookahead=lookahead,
                    consume_nonmatches=True,
                )
        except Exception as e:  # pylint: disable=broad-except
            print(f"Exception raised when waiting for attribute change: {e}")
        finally:
            device_proxy.unsubscribe_event(subscription_id)


class _CommandDrivenAttributeAccess:
    """A descriptor class for _CommandDrivenAttributeAccess."""

    def __init__(
        self: _CommandDrivenAttributeAccess, command_name: str, attr_name: str
    ) -> None:
        """
        Initialise a new _CommandDrivenAttributeAccess.

        :param command_name: the name of the command
        :param attr_name: the name of the attribute
        """
        self.__attr_name = attr_name
        self.__command_name = command_name

    def __get__(
        self: _CommandDrivenAttributeAccess, obj: TileWrapper, objtype: Any = None
    ) -> Any:
        """
        Get method.

        :param obj: the obj
        :param objtype: the objtype

        :returns: the attribute value.
        """
        return getattr(obj._tile_device, self.__attr_name)

    def __set__(
        self: _CommandDrivenAttributeAccess, obj: TileWrapper, value: Any
    ) -> None:
        """
        Set method.

        :param obj: the obj
        :param value: the value
        """
        getattr(obj._tile_device, self.__command_name)(value)

        AttributeWaiter(timeout=2).wait_for_value(
            obj._tile_device, self.__attr_name, value
        )


class _AttributeAccess:
    """A descriptor class for attribute."""

    def __init__(self: _AttributeAccess, attr_name: str) -> None:
        """
        Initialise a new _AttributeAccess.

        :param attr_name: the name of the attribute
        """
        self.__attr_name = attr_name

    def __get__(self: _AttributeAccess, obj: TileWrapper, objtype: Any = None) -> Any:
        """
        Get method.

        :param obj: the obj
        :param objtype: the objtype

        :returns: The attribute value.
        """
        return getattr(obj._tile_device, self.__attr_name)

    def __set__(self: _AttributeAccess, obj: TileWrapper, value: Any) -> None:
        """
        Set method.

        :param obj: the obj
        :param value: the value
        """
        setattr(obj._tile_device, self.__attr_name, value)

        AttributeWaiter(timeout=2).wait_for_value(
            obj._tile_device, self.__attr_name, value
        )


class _ProgrammingStateAccess:
    """A descriptor class for tileprogrammingstate."""

    def __get__(
        self: _ProgrammingStateAccess, obj: TileWrapper, objtype: Any = None
    ) -> Any:
        """
        Get method.

        :param obj: the obj
        :param objtype: the objtype

        :returns: the tileprogrammingstate.
        """
        return obj._tile_device.tileProgrammingState

    def __set__(self: _ProgrammingStateAccess, obj: TileWrapper, value: Any) -> None:
        """
        Set method.

        :param obj: the obj
        :param value: the value

        :raises NotImplementedError: when the TPM cannot be driven
            to the desired state.
        """
        obj._tile_device.adminMOde = 0
        time.sleep(1)
        match value:
            case TpmStatus.OFF:
                obj._tile_device.Off()
            case TpmStatus.UNPROGRAMMED:
                if obj._tile_device.tileProgrammingState == "Off":
                    obj._tile_device.On()
                    AttributeWaiter(timeout=30).wait_for_value(
                        obj._tile_device,
                        "tileProgrammingState",
                        "Initialised",
                        lookahead=5,
                    )
                # trigger a overheating event.
                obj._tile_device.adminMode = 2
                obj._tile_device.SetFirmwareTemperatureThresholds(
                    json.dumps({"board_temperature_threshold": [22.0, 32.0]})
                )

            case TpmStatus.INITIALISED:
                obj._tile_device.globalReferenceTime = ""
                if obj._tile_device.tileProgrammingState == "Synchronised":
                    obj._tile_device.globalReferenceTime = ""
                    obj._tile_device.Initialise()
                    AttributeWaiter(timeout=30).wait_for_value(
                        obj._tile_device,
                        "tileProgrammingState",
                        "Initialised",
                        lookahead=5,
                    )
                if obj._tile_device.tileProgrammingState == "Initialised":
                    obj._tile_device.Initialise()
                    AttributeWaiter(timeout=30).wait_for_value(
                        obj._tile_device,
                        "tileProgrammingState",
                        "Initialised",
                        lookahead=5,
                    )
                else:
                    obj._tile_device.globalReferenceTime = ""
                    obj._tile_device.Off()
                    AttributeWaiter(timeout=30).wait_for_value(
                        obj._tile_device,
                        "tileProgrammingState",
                        "Off",
                        lookahead=5,
                    )
                    obj._tile_device.On()
                    AttributeWaiter(timeout=30).wait_for_value(
                        obj._tile_device,
                        "tileProgrammingState",
                        "Initialised",
                        lookahead=5,
                    )
            case TpmStatus.SYNCHRONISED:
                start_time = datetime.strftime(
                    datetime.fromtimestamp(time.time() + 2), RFC_FORMAT
                )
                obj._tile_device.globalReferenceTime = start_time
                obj._tile_device.On()
            case _:
                raise NotImplementedError("Not yet able to drive TPM to this state.")

        AttributeWaiter(timeout=30).wait_for_value(
            obj._tile_device,
            "tileProgrammingState",
            TpmStatus(value).pretty_name(),
            lookahead=5,
        )


class _AttributeReadOnlyAccess:  # pylint: disable=too-few-public-methods
    """A descriptor class."""

    def __init__(self: _AttributeReadOnlyAccess, attr_name: str) -> None:
        """
        Initialise a new _AttributeReadOnlyAccess.

        :param attr_name: the name of the attribute
        """
        self.__attr_name = attr_name

    def __get__(
        self: _AttributeReadOnlyAccess, obj: TileWrapper, objtype: Any = None
    ) -> Any:
        """
        Get method.

        :param obj: the obj
        :param objtype: the objtype

        :returns: the attribute value.
        """
        return getattr(obj._tile_device, self.__attr_name)


class TileWrapper:  # pylint: disable=too-few-public-methods
    """
    The tile wrapper will wrap the tile DeviceProxy.

    This is used for testing to allow a flat API allowing
    us to drive the state hiding details of the API in
    descriptors.
    """

    tile_programming_state = _ProgrammingStateAccess()

    beamformer_table = _CommandDrivenAttributeAccess(
        "SetBeamFormerRegions", "beamformerTable"
    )
    beamformer_table = _CommandDrivenAttributeAccess(
        "SetBeamFormerRegions", "beamformerTable"
    )

    preadu_levels = _AttributeAccess("preaduLevels")
    csp_rounding = _AttributeAccess("cspRounding")
    static_time_delays = _AttributeAccess("staticTimeDelays")
    channeliser_rounding = _AttributeAccess("channeliserRounding")
    global_reference_time = _AttributeAccess("globalReferenceTime")
    health_model_params = _AttributeAccess("healthModelParams")
    srcip40gfpga1 = _AttributeAccess("srcip40gfpga1")
    srcip40gfpga2 = _AttributeAccess("srcip40gfpga2")
    csp_spead_format = _AttributeAccess("cspSpeadFormat")
    logical_tile_id = _AttributeAccess("logicalTileId")
    station_id = _AttributeAccess("stationId")
    firmware_name = _AttributeAccess("firmwareName")
    firmware_version = _AttributeAccess("firmwareVersion")
    antenna_ids = _AttributeAccess("antennaIds")
    phase_terminal_count = _AttributeAccess("phaseTerminalCount")

    # READ ONLY
    adc_pll_status = _AttributeReadOnlyAccess("adc_pll_status")
    tile_beamformer_status = _AttributeReadOnlyAccess("tile_beamformer_status")
    station_beamformer_status = _AttributeReadOnlyAccess("station_beamformer_status")
    station_beamformer_error_count = _AttributeReadOnlyAccess(
        "station_beamformer_error_count"
    )
    station_beamformer_flagged_count = _AttributeReadOnlyAccess(
        "station_beamformer_flagged_count"
    )
    crc_error_count = _AttributeReadOnlyAccess("crc_error_count")

    bip_error_count = _AttributeReadOnlyAccess("bip_error_count")
    decode_error_count = _AttributeReadOnlyAccess("decode_error_count")
    linkup_loss_count = _AttributeReadOnlyAccess("linkup_loss_count")
    data_router_status = _AttributeReadOnlyAccess("data_router_status")
    data_router_discarded_packets = _AttributeReadOnlyAccess(
        "data_router_discarded_packets"
    )
    arp = _AttributeReadOnlyAccess("arp")
    udp_status = _AttributeReadOnlyAccess("udp_status")
    ddr_initialisation = _AttributeReadOnlyAccess("ddr_initialisation")

    ddr_reset_counter = _AttributeReadOnlyAccess("ddr_reset_counter")
    f2f_soft_errors = _AttributeReadOnlyAccess("f2f_soft_errors")
    f2f_hard_errors = _AttributeReadOnlyAccess("f2f_hard_errors")
    resync_count = _AttributeReadOnlyAccess("resync_count")
    lane_status = _AttributeReadOnlyAccess("lane_status")
    lane_error_count = _AttributeReadOnlyAccess("lane_error_count")
    clock_managers = _AttributeReadOnlyAccess("clock_managers")
    clocks = _AttributeReadOnlyAccess("clocks")
    adc_sysref_counter = _AttributeReadOnlyAccess("adc_sysref_counter")
    adc_sysref_timing_requirements = _AttributeReadOnlyAccess(
        "adc_sysref_timing_requirements"
    )
    f2f_pll_status = _AttributeReadOnlyAccess("f2f_pll_status")
    qpll_status = _AttributeReadOnlyAccess("qpll_status")
    timing_pll_status = _AttributeReadOnlyAccess("timing_pll_status")
    tile_info = _AttributeReadOnlyAccess("tile_info")
    voltages = _AttributeReadOnlyAccess("voltages")

    temperatures = _AttributeReadOnlyAccess("temperatures")
    currents = _AttributeReadOnlyAccess("currents")
    timing = _AttributeReadOnlyAccess("timing")
    io = _AttributeReadOnlyAccess("io")
    dsp = _AttributeReadOnlyAccess("dsp")
    adcs = _AttributeReadOnlyAccess("adcs")
    I2C_access_alm = _AttributeReadOnlyAccess("I2C_access_alm")
    temperature_alm = _AttributeReadOnlyAccess("temperature_alm")
    SEM_wd = _AttributeReadOnlyAccess("SEM_wd")
    MCU_wd = _AttributeReadOnlyAccess("MCU_wd")
    csp_destination_ip = _AttributeReadOnlyAccess("cspDestinationIp")
    csp_destination_mac = _AttributeReadOnlyAccess("cspDestinationMac")
    csp_destination_port = _AttributeReadOnlyAccess("cspDestinationPort")

    def __init__(self: TileWrapper, tile_device: tango.DeviceProxy) -> None:
        """
        Initialise a new TileWrapper.

        :param tile_device: the tango.DeviceProxy we are wrapping.
        """
        self._tile_device = tile_device

    def set_state(self: TileWrapper, programming_state: int, **kwargs: Any) -> None:
        """
        Set the state of the TPM.

        :param programming_state: A mandatory argument to drive the state to the
            correct TileProgrammingState
        :param kwargs: Optional kwargs to populate state.
        """
        self.tile_programming_state = programming_state
        for kwarg, val in kwargs.items():
            setattr(self, kwarg, val)
