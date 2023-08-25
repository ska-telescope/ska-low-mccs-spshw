# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE.txt for more info.
"""
This module implements a simple DAQ receiver.

It exists to allow MccsDaqReceiver to be unit tested.
"""
from __future__ import annotations

import functools
import json
import os
import time
from enum import IntEnum
from typing import Any, Callable, Iterator, Optional, TypeVar, cast

from pyaavs import station
from ska_control_model import ResultCode, TaskStatus
from ska_low_mccs_daq_interface import run_server_forever

__all__ = ["DaqSimulator"]

Wrapped = TypeVar("Wrapped", bound=Callable[..., Any])


def check_initialisation(func: Wrapped) -> Wrapped:
    """
    Return a function that checks component initialisation before calling.

    This function is intended to be used as a decorator:

    .. code-block:: python

        @check_initialisation
        def scan(self):
            ...

    :param func: the wrapped function

    :return: the wrapped function
    """

    @functools.wraps(func)
    def _wrapper(
        self: DaqSimulator,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Check for component initialisation before calling the function.

        This is a wrapper function that implements the functionality of
        the decorator.

        :param self: This instance of an DaqSimulator.
        :param args: positional arguments to the wrapped function
        :param kwargs: keyword arguments to the wrapped function

        :raises ValueError: if component initialisation has
            not been completed.
        :return: whatever the wrapped function returns
        """
        if not self.initialised:
            raise ValueError(
                f"Cannot execute '{type(self).__name__}.{func.__name__}'. "
                "DaqReceiver has not been initialised. "
                "Set adminMode to ONLINE to re-initialise."
            )
        return func(self, *args, **kwargs)

    return cast(Wrapped, _wrapper)


# TODO: Redefined for now, to avoid having to import from pydaq.
# This really should not be exposed through the control interface at all.
class DaqModes(IntEnum):
    """Data acquisition modes."""

    RAW_DATA = 0
    CHANNEL_DATA = 1
    BEAM_DATA = 2
    CONTINUOUS_CHANNEL_DATA = 3
    INTEGRATED_BEAM_DATA = 4
    INTEGRATED_CHANNEL_DATA = 5
    STATION_BEAM_DATA = 6
    CORRELATOR_DATA = 7
    ANTENNA_BUFFER = 8


def convert_daq_modes(consumers_to_start: str) -> list[DaqModes]:
    """
    Convert a string representation of DaqModes into a list of DaqModes.

    Breaks a comma separated list into a list of words,
        strips whitespace and extracts the `enum` part and casts the string
        into a DaqMode or directly cast an int into a DaqMode.

    :param consumers_to_start: A string containing a comma separated
        list of DaqModes.

    :return: a converted list of DaqModes or an empty
        list if no consumers supplied.
    """
    if consumers_to_start != "":
        consumer_list = consumers_to_start.split(",")
        converted_consumer_list = []
        for consumer in consumer_list:
            try:
                # Convert string representation of a DaqMode.
                converted_consumer = DaqModes[consumer.strip().split(".")[-1]]
            except KeyError:
                # Convert string representation of an int.
                converted_consumer = DaqModes(int(consumer))
            converted_consumer_list.append(converted_consumer)
        return converted_consumer_list
    return []


class DaqSimulator:
    """An implementation of a DaqSimulator device."""

    def __init__(self: DaqSimulator):
        """Initialise this device."""
        self._initialised = False

        self._config = {
            "observation_metadata": "foo",
            "receiver_ports": "bah",
            "append_integrated": False,
        }

        self._modes: list[DaqModes] = []

        self._stop_bandpass: bool = False
        self._monitoring_bandpass: bool = False

    def initialise(
        self: DaqSimulator, config: dict[str, Any]
    ) -> tuple[ResultCode, str]:
        """
        Initialise a new DaqReceiver instance.

        :param config: the configuration to apply

        :return: a resultcode, message tuple
        """
        if self._initialised:
            return ResultCode.REJECTED, "Daq already initialised"
        self._config.update(config)
        self._initialised = True
        return ResultCode.OK, "Daq successfully initialised"

    @property
    def initialised(self: DaqSimulator) -> bool:
        """
        Return whether the simulated DAQ is initialised.

        :return: whether the simulated DAQ is initialised.
        """
        return self._initialised

    @check_initialisation
    def start(
        self: DaqSimulator,
        modes_to_start: str,
    ) -> Iterator[str | tuple[str, str]]:
        """
        Start data acquisition with the current configuration.

        A infinite streaming loop will be started until told to stop.
        This will notify the client of state changes and metadata
        of files written to disk, e.g. `data_type`.`file_name`.

        :param modes_to_start: string listing the modes to start.

        :yield: a status update.
        """
        print("SIMULATOR START")
        self._modes = convert_daq_modes(modes_to_start)
        yield "LISTENING"

        # yield somethin' else
        yield "STOPPED"

    @check_initialisation
    def stop(self: DaqSimulator) -> tuple[ResultCode, str]:
        """
        Stop data acquisition.

        :return: a resultcode, message tuple
        """
        self._modes = []
        return ResultCode.OK, "Daq stopped"

    @check_initialisation
    def configure(
        self: DaqSimulator, config: dict[str, Any]
    ) -> tuple[ResultCode, str]:  # noqa: E501
        """
        Apply a configuration to the DaqReceiver.

        :param config: the configuration to apply

        :return: a resultcode, message tuple
        """
        if config:
            self._config.update(config)
            return ResultCode.OK, "Daq reconfigured"
        return ResultCode.REJECTED, "No configuration data supplied."

    @check_initialisation
    def get_configuration(
        self: DaqSimulator,
    ) -> dict[str, Any]:
        """
        Retrieve the current DAQ configuration.

        :return: a configuration dictionary.
        """
        config: dict[str, Any] = self._config.copy()
        try:
            port = cast(int, config["receiver_ports"])
        except ValueError:
            pass
        except TypeError:
            ports = [str(port) for port in config["receiver_ports"]]
            config["receiver_ports"] = "[" + ",".join(ports) + "]"
        else:
            config["receiver_ports"] = f"[{port}]"
        return config

    @check_initialisation
    def get_status(self: DaqSimulator) -> dict[str, Any]:
        """
        Provide status information for this MccsDaqReceiver.

        This method returns status as a json string with entries for:
            - Running Consumers: [DaqMode.name: str, DaqMode.value: int]
            - Receiver Interface: "Interface Name": str
            - Receiver Ports: [Port_List]: list[int]
            - Receiver IP: "IP_Address": str

        :return: A json string containing the status of this DaqReceiver.
        """
        # 2. Get consumer list, filter by `running`
        running_consumers = [[mode.name, int(mode)] for mode in self._modes]
        return {
            "Running Consumers": running_consumers,
            "Receiver Interface": self._config.get("receiver_interface", 0),
            "Receiver Ports": self._config.get("receiver_ports", ""),
            "Receiver IP": [self._config.get("receiver_ip", "")],
            "Bandpass Monitor": self._monitoring_bandpass,
        }

    # pylint: disable=too-many-return-statements
    @check_initialisation
    def start_bandpass_monitor(
        self: DaqSimulator,
        argin: str,
    ) -> Iterator[tuple[TaskStatus, str, str|None, str|None, str|None]]:
        """
        Start monitoring antenna bandpasses.

        The MccsDaqReceiver will begin monitoring antenna bandpasses
            and producing plots of the spectra.

        :param argin: A json dictionary with keywords
            - station_config_path
            Path to a station configuration file.
            - plot_directory
            Directory in which to store bandpass plots.
            - monitor_rms
            Whether or not to additionally produce RMS plots.
            Default: False.
            - auto_handle_daq
            Whether DAQ should be automatically reconfigured,
            started and stopped without user action if necessary.
            This set to False means we expect DAQ to already
            be properly configured and listening for traffic
            and DAQ will not be stopped when `StopBandpassMonitor`
            is called.
            Default: False.

        :return: a task status and response message
        """
        if self._monitoring_bandpass:
            yield (TaskStatus.REJECTED, "Bandpass monitor is already active.", None, None, None)
            return

        self._stop_bandpass = False
        params: dict[str, Any] = json.loads(argin)
        try:
            station_config_path: str = params["station_config_path"]
            plot_directory: str = params["plot_directory"]
        except KeyError:
            yield (
                TaskStatus.REJECTED,
                "Param `argin` must have keys for `station_config_path` "
                "and `plot_directory`", None, None, None
            )
            return
        auto_handle_daq: bool = cast(bool, params.get("auto_handle_daq", False))
        if self._config["append_integrated"]:
            if not auto_handle_daq:
                yield (
                    TaskStatus.REJECTED,
                    "Current DAQ config is invalid. "
                    "The `append_integrated` option must be set to false "
                    "for bandpass monitoring.", None, None, None
                )
                return
            self.configure({"append_integrated": False})

        if "INTEGRATED_CHANNEL_DATA" not in self._modes:
            if not auto_handle_daq:
                yield (
                    TaskStatus.REJECTED,
                    "INTEGRATED_CHANNEL_DATA consumer must be running "
                    "before bandpasses can be monitored.", None, None, None
                )
                return
            self.start(modes_to_start="INTEGRATED_CHANNEL_DATA")

        if not os.path.exists(station_config_path) or not os.path.isfile(
            station_config_path
        ):
            yield (
                TaskStatus.REJECTED,
                f"Specified configuration file ({station_config_path}) does not exist.", None, None, None
            )
            return

        station.load_configuration_file(station_config_path)
        station_conf = station.configuration
        # Extract station name
        station_name = station_conf["station"]["name"]
        if station_name.upper() == "UNNAMED":
            yield (
                TaskStatus.REJECTED,
                "Please set station name in configuration file "
                f"{station_config_path}, currently unnamed.", None, None, None
            )
            return

        # Check that the station is configured to transmit data over 1G
        if station_conf["network"]["lmc"]["use_teng_integrated"]:
            yield (
                TaskStatus.REJECTED,
                f"Station {station_config_path} must be configured to send "
                "integrated data over the 1G network, and each station should "
                "define a different destination port. Please check", None, None, None
            )
            return

        # Create plotting directory structure
        if not self.create_plotting_directory(plot_directory, station_name):
            yield (
                TaskStatus.FAILED,
                f"Unable to create plotting directory at: {plot_directory}", None, None, None
            )
            return

        self._monitoring_bandpass = True
        yield (TaskStatus.IN_PROGRESS, "Bandpass monitor active", None, None, None)

        i=0 # So the attribute can iterate.
        while not self._stop_bandpass:
            yield (TaskStatus.IN_PROGRESS, "plot sent", f"fake_x_bandpass_plot_{i}", f"fake_y_bandpass_plot_{i}", f"fake_rms_plot_{i}",)
            i+=1
            time.sleep(5)

        if auto_handle_daq:
            self.stop()
        self._monitoring_bandpass = False

        yield (TaskStatus.COMPLETED, "Bandpass monitoring complete.", None, None, None)

    def stop_bandpass_monitor(self: DaqSimulator) -> tuple[ResultCode, str]:
        """
        Stop monitoring antenna bandpasses.

        :return: a resultcode, message tuple
        """
        self._stop_bandpass = True
        return (ResultCode.OK, "Bandpass monitor stopping.")

    def create_plotting_directory(
        self: DaqSimulator,
        parent: str,
        station_name: str,
    ) -> bool:
        """
        Create plotting directory structure for this station.

        This method will always return `True` unless parent=="invalid_directory"

        :param parent: Parent plotting directory
        :param station_name: Station name

        :return: `False` if parent=="invalid_directory" else `True`
        """
        return not (parent == "invalid_directory")


def main() -> None:
    """Entry point for a gRPC server that fronts a DAQ simulator."""
    daq_simulator = DaqSimulator()

    port = int(os.getenv("DAQ_SIMULATOR_PORT", "50051"))
    run_server_forever(daq_simulator, port)


if __name__ == "__main__":
    main()
