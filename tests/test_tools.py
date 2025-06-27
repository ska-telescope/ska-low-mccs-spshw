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


def wait_for_lrc_result(
    device: tango.DeviceProxy, uid: str, expected_result: ResultCode, timeout: float
) -> None:
    """
    Wait for a specific result from a LRC.

    :param device: The tango device to listen to.
    :param uid: The uid used to identify the task under question.
    :param expected_result: The expected ResultCode from execution.
    :param timeout: A time to wait in seconds.

    :raises TimeoutError: When the commands failed to exit the queue in time.
    :raises ValueError: When the Result is incorrect or the result not found.
    """
    count: int = 0
    increment: int = 1

    while device.lrcQueue != () or device.lrcExecuting != ():
        time.sleep(increment)
        count += increment
        if count == timeout:
            raise TimeoutError(
                f"LRCs still running after {timeout} seconds: "
                f"{device.dev_name()} : {device.lrcQueue=} "
                f"{device.lrcExecuting=}"
            )

    for finished_result in device.lrcfinished:
        loaded_result = json.loads(finished_result)
        if loaded_result["uid"] == uid:
            actual_result = ResultCode(loaded_result["result"][0])
            if actual_result == expected_result:
                return
            raise ValueError(
                f"Result for {uid} = {actual_result}. Expected {expected_result}"
            )
    raise ValueError(f"uid '{uid}' not found in LrcFinished")


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

    # (wrapper_attr_name, device_attr_name) pairs
    # for assigning _AttributeAccess descriptors
    _rw_attrs = [
        ("preadu_levels", "preaduLevels"),
        ("csp_rounding", "cspRounding"),
        ("static_time_delays", "staticTimeDelays"),
        ("channeliser_rounding", "channeliserRounding"),
        ("global_reference_time", "globalReferenceTime"),
        ("health_model_params", "healthModelParams"),
        ("srcip40gfpga1", "srcip40gfpga1"),
        ("srcip40gfpga2", "srcip40gfpga2"),
        ("csp_spead_format", "cspSpeadFormat"),
        ("logical_tile_id", "logicalTileId"),
        ("station_id", "stationId"),
        ("firmware_name", "firmwareName"),
        ("firmware_version", "firmwareVersion"),
        ("antenna_ids", "antennaIds"),
        ("phase_terminal_count", "phaseTerminalCount"),
    ]
    for name, api_name in _rw_attrs:
        locals()[name] = _AttributeAccess(api_name)

    # (wrapper_attr_name, device_attr_name) pairs
    # for assigning _AttributeReadOnlyAccess descriptors
    _ro_attrs = [
        ("adc_pll_status", "adc_pll_status"),
        ("tile_beamformer_status", "tile_beamformer_status"),
        ("station_beamformer_status", "station_beamformer_status"),
        ("station_beamformer_error_count", "station_beamformer_error_count"),
        ("station_beamformer_flagged_count", "station_beamformer_flagged_count"),
        ("crc_error_count", "crc_error_count"),
        ("bip_error_count", "bip_error_count"),
        ("decode_error_count", "decode_error_count"),
        ("linkup_loss_count", "linkup_loss_count"),
        ("data_router_status", "data_router_status"),
        ("data_router_discarded_packets", "data_router_discarded_packets"),
        ("arp", "arp"),
        ("udp_status", "udp_status"),
        ("ddr_initialisation", "ddr_initialisation"),
        ("ddr_reset_counter", "ddr_reset_counter"),
        ("f2f_soft_errors", "f2f_soft_errors"),
        ("f2f_hard_errors", "f2f_hard_errors"),
        ("resync_count", "resync_count"),
        ("lane_status", "lane_status"),
        ("lane_error_count", "lane_error_count"),
        ("clock_managers", "clock_managers"),
        ("clocks", "clocks"),
        ("adc_sysref_counter", "adc_sysref_counter"),
        ("adc_sysref_timing_requirements", "adc_sysref_timing_requirements"),
        ("f2f_pll_status", "f2f_pll_status"),
        ("qpll_status", "qpll_status"),
        ("timing_pll_status", "timing_pll_status"),
        ("tile_info", "tile_info"),
        ("voltages", "voltages"),
        ("temperatures", "temperatures"),
        ("currents", "currents"),
        ("timing", "timing"),
        ("io", "io"),
        ("dsp", "dsp"),
        ("adcs", "adcs"),
        ("I2C_access_alm", "I2C_access_alm"),
        ("temperature_alm", "temperature_alm"),
        ("SEM_wd", "SEM_wd"),
        ("MCU_wd", "MCU_wd"),
        ("csp_destination_ip", "cspDestinationIp"),
        ("csp_destination_mac", "cspDestinationMac"),
        ("csp_destination_port", "cspDestinationPort"),
    ]
    for name, api_name in _ro_attrs:
        locals()[name] = _AttributeReadOnlyAccess(api_name)

    # Clean up to avoid leaking variables
    del name, api_name, _rw_attrs, _ro_attrs

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
