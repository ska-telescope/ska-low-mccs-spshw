# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the daq component manager."""
from __future__ import annotations

import json
import time

import pytest
from ska_control_model import CommunicationStatus, ResultCode, TaskStatus
from ska_tango_testing.mock import MockCallableGroup

from ska_low_mccs_spshw.daq_receiver import DaqComponentManager
from ska_low_mccs_spshw.daq_receiver.daq_simulator import DaqModes, convert_daq_modes


class TestDaqComponentManager:
    """Tests of the Daq Receiver component manager."""

    def test_communication(
        self: TestDaqComponentManager,
        daq_component_manager: DaqComponentManager,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the daq component manager's management of communication.

        :param daq_component_manager: the daq component manager
            under test.
        :param callbacks: a dictionary from which callbacks with
            asynchrony support can be accessed.
        """
        assert daq_component_manager.communication_state == CommunicationStatus.DISABLED

        daq_component_manager.start_communicating()

        # allow some time for device communication to start before testing
        time.sleep(0.1)

        callbacks["communication_state"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_state"].assert_call(CommunicationStatus.ESTABLISHED)
        assert (
            daq_component_manager.communication_state == CommunicationStatus.ESTABLISHED
        )

        daq_component_manager.stop_communicating()
        callbacks["communication_state"].assert_call(CommunicationStatus.DISABLED)
        assert daq_component_manager.communication_state == CommunicationStatus.DISABLED

    def test_admin_mode_behaviour(
        self: TestDaqComponentManager,
        daq_component_manager: DaqComponentManager,
        callbacks: MockCallableGroup,
    ) -> None:
        """
        Test the daq component manager's management of communication.

        Here we test that we only connect to our DaqReceiver once
            start_communicating is called and that cycling adminMode
            (by calling stop_communicating then start_communicating)
            does not reinitialise the DaqReceiver.

        :param daq_component_manager: the daq component manager
            under test.
        :param callbacks: a dictionary from which callbacks with
            asynchrony support can be accessed.
        """
        # 1. Establish comms with DaqReceiver.
        assert daq_component_manager.communication_state == CommunicationStatus.DISABLED
        daq_component_manager.start_communicating()
        time.sleep(0.1)

        callbacks["communication_state"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_state"].assert_call(CommunicationStatus.ESTABLISHED)
        assert (
            daq_component_manager.communication_state == CommunicationStatus.ESTABLISHED
        )

        # 2. Configure DAQ to a non-standard config.
        non_standard_config = {
            "receiver_ports": "9876",
            "nof_tiles": 55,
            "nof_channels": 1234,
        }
        daq_component_manager.configure_daq(json.dumps(non_standard_config))

        # 3. Assert config was applied.
        daq_config_dict = daq_component_manager.get_configuration()
        assert daq_config_dict["receiver_ports"] == "[9876]"
        assert daq_config_dict["nof_tiles"] == 55
        assert daq_config_dict["nof_channels"] == 1234

        # 4. Imitate adminMode cycling by calling stop/start comms.
        daq_component_manager.stop_communicating()
        callbacks["communication_state"].assert_call(CommunicationStatus.DISABLED)
        assert daq_component_manager.communication_state == CommunicationStatus.DISABLED
        daq_component_manager.start_communicating()
        time.sleep(0.1)

        callbacks["communication_state"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_state"].assert_call(CommunicationStatus.ESTABLISHED)
        assert (
            daq_component_manager.communication_state == CommunicationStatus.ESTABLISHED
        )

        # 5. Assert that our previously set config remains valid.
        daq_config_dict = daq_component_manager.get_configuration()
        assert daq_config_dict["receiver_ports"] == "[9876]"
        assert daq_config_dict["nof_tiles"] == 55
        assert daq_config_dict["nof_channels"] == 1234

    # Not compiled with correlator currently.
    @pytest.mark.parametrize(
        ("daq_modes_str", "daq_modes_list"),
        (
            ("DaqModes.RAW_DATA", [DaqModes.RAW_DATA]),
            ("DaqModes.CHANNEL_DATA", [DaqModes.CHANNEL_DATA]),
            ("DaqModes.BEAM_DATA", [DaqModes.BEAM_DATA]),
            ("DaqModes.CONTINUOUS_CHANNEL_DATA", [DaqModes.CONTINUOUS_CHANNEL_DATA]),
            ("DaqModes.INTEGRATED_BEAM_DATA", [DaqModes.INTEGRATED_BEAM_DATA]),
            ("DaqModes.INTEGRATED_CHANNEL_DATA", [DaqModes.INTEGRATED_CHANNEL_DATA]),
            ("DaqModes.STATION_BEAM_DATA", [DaqModes.STATION_BEAM_DATA]),
            # ("DaqModes.CORRELATOR_DATA", [DaqModes.CORRELATOR_DATA]),
            ("DaqModes.ANTENNA_BUFFER", [DaqModes.ANTENNA_BUFFER]),
            (
                "DaqModes.CHANNEL_DATA, DaqModes.BEAM_DATA, DaqModes.RAW_DATA",
                [DaqModes.CHANNEL_DATA, DaqModes.BEAM_DATA, DaqModes.RAW_DATA],
            ),
            ("1, 2, 0", [DaqModes.CHANNEL_DATA, DaqModes.BEAM_DATA, DaqModes.RAW_DATA]),
            (
                "DaqModes.CONTINUOUS_CHANNEL_DATA, DaqModes.ANTENNA_BUFFER, 6",
                [
                    DaqModes.CONTINUOUS_CHANNEL_DATA,
                    DaqModes.ANTENNA_BUFFER,
                    DaqModes.STATION_BEAM_DATA,
                ],
            ),
            (
                "5, 4, DaqModes.STATION_BEAM_DATA",
                [
                    DaqModes.INTEGRATED_CHANNEL_DATA,
                    DaqModes.INTEGRATED_BEAM_DATA,
                    DaqModes.STATION_BEAM_DATA,
                ],
            ),
            (
                "RAW_DATA, 3, DaqModes.STATION_BEAM_DATA, ANTENNA_BUFFER",
                [
                    DaqModes.RAW_DATA,
                    DaqModes.CONTINUOUS_CHANNEL_DATA,
                    DaqModes.STATION_BEAM_DATA,
                    DaqModes.ANTENNA_BUFFER,
                ],
            ),
            ("", []),
        ),
    )
    def test_convert_daq_modes(
        self: TestDaqComponentManager,
        daq_modes_str: str,
        daq_modes_list: list[DaqModes],
    ) -> None:
        """
        Test DaqModes can be properly converted.

        This tests that DaqModes can be converted properly from a comma separated list
            of ints and/or DaqModes to a list of DaqModes.

        :param daq_modes_str: A comma separated list of DaqModes and/or ints.
        :param daq_modes_list: The expected output of the conversion function.
        """
        # converted_daq_modes = convert_daq_modes(daq_modes_str)
        assert convert_daq_modes(daq_modes_str) == daq_modes_list
        # assert len(converted_daq_modes) == len(daq_modes_list)
        # for i, mode in enumerate(converted_daq_modes):
        #     print(f"mode: {mode} -- expected: {daq_modes_list[i]}")
        #     assert mode == daq_modes_list[i]

    @pytest.mark.parametrize(
        "daq_modes",
        (
            "DaqModes.RAW_DATA",
            "DaqModes.CHANNEL_DATA",
            "DaqModes.BEAM_DATA",
            "DaqModes.CONTINUOUS_CHANNEL_DATA",
            "DaqModes.INTEGRATED_BEAM_DATA",
            "DaqModes.INTEGRATED_CHANNEL_DATA",
            "DaqModes.STATION_BEAM_DATA",
            # "DaqModes.CORRELATOR_DATA",  # Not compiled with correlator currently.
            "DaqModes.ANTENNA_BUFFER",
            "DaqModes.CHANNEL_DATA, DaqModes.BEAM_DATA, DaqModes.RAW_DATA",
            "1, 2, 0",
            "DaqModes.CONTINUOUS_CHANNEL_DATA, DaqModes.ANTENNA_BUFFER, 6",
            "5, 4, DaqModes.STATION_BEAM_DATA",
        ),
    )
    def test_instantiate_daq(
        self: TestDaqComponentManager,
        daq_component_manager: DaqComponentManager,
        callbacks: MockCallableGroup,
        daq_modes: str,
    ) -> None:
        """
        Test basic DAQ functionality.

        This test merely instantiates DAQ, starts a consumer,
            waits for a time and then stops the consumer.
            This also doubles as a check that we can start and stop every consumer.

        :param daq_component_manager: the daq receiver component manager
            under test.
        :param callbacks: a dictionary from which callbacks with
            asynchrony support can be accessed.
        :param daq_modes: The DAQ consumers to start.
        """
        acquisition_duration = 2

        daq_component_manager.start_communicating()
        callbacks["communication_state"].assert_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        callbacks["communication_state"].assert_call(CommunicationStatus.ESTABLISHED)

        daq_config = {
            "acquisition_duration": acquisition_duration,
            "directory": ".",
        }
        daq_component_manager.configure_daq(json.dumps(daq_config))

        # Start DAQ and check our consumer is running.
        # Need exactly 1 callback per consumer started or None. Cast for Mypy.
        ts, message = daq_component_manager.start_daq(
            daq_modes,
            task_callback=callbacks["task_start_daq"],
        )
        # assert rc == ResultCode.OK.value
        # assert message == "Daq started"
        assert ts == TaskStatus.QUEUED
        assert message == "Task queued"

        # TODO: Why is this queued 2 times?
        callbacks["task_start_daq"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task_start_daq"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task_start_daq"].assert_call(
            status=TaskStatus.IN_PROGRESS, result="Start Command issued to gRPC stub"
        )
        callbacks["task_start_daq"].assert_call(
            status=TaskStatus.COMPLETED, result="Daq has been started and is listening"
        )

        converted_daq_modes: list[DaqModes] = convert_daq_modes(daq_modes)
        # for mode in daq_modes:
        # If we're using ints instead of DaqModes make the conversion so we
        # can check the consumer.
        # mode_to_check = DaqModes(mode)
        # status will not have health info when cpt mgr method is directly called.
        status = json.loads(daq_component_manager.daq_status())

        running_consumers = status["Running Consumers"]

        for i, mode_to_check in enumerate(converted_daq_modes):
            assert mode_to_check.value in running_consumers[i]

        # Wait for data etc
        time.sleep(acquisition_duration)

        # Stop DAQ and check our consumer is not running.
        rc, message = daq_component_manager.stop_daq(task_callback=callbacks["task"])
        assert rc == ResultCode.OK.value
        assert message == "Daq stopped"

        # callbacks["task"].assert_call(status=TaskStatus.QUEUED)
        callbacks["task"].assert_call(status=TaskStatus.IN_PROGRESS)
        callbacks["task"].assert_call(status=TaskStatus.COMPLETED)
        # Once we issue the stop command on the DAQ this will stop the thread
        # with the streamed response. We need to wait for the start_daq thread
        # to complete.

        # for mode in daq_modes:
        # If we're using ints instead of DaqModes make the conversion so we
        # can check the consumer.
        # mode_to_check = DaqModes(mode)
        # TODO: Cannot check status of consumers until DaqStatus cmd is updated.
        # assert not daq_component_manager.daq_instance._running_consumers[
        #     mode_to_check
        # ]

    @pytest.mark.parametrize(
        "consumer_list",
        (
            "DaqModes.RAW_DATA",
            "DaqModes.CHANNEL_DATA",
            "DaqModes.BEAM_DATA",
            "DaqModes.CONTINUOUS_CHANNEL_DATA",
            "DaqModes.INTEGRATED_BEAM_DATA",
            "DaqModes.INTEGRATED_CHANNEL_DATA",
            "DaqModes.STATION_BEAM_DATA",
            "DaqModes.CORRELATOR_DATA",
            "DaqModes.ANTENNA_BUFFER",
            "",  # Default behaviour.
            "DaqModes.INTEGRATED_BEAM_DATA,ANTENNA_BUFFER, BEAM_DATA",
            "DaqModes.INTEGRATED_CHANNEL_DATA",
        ),
    )
    def test_set_get_consumer_list(
        self: TestDaqComponentManager,
        daq_component_manager: DaqComponentManager,
        consumer_list: str,
    ) -> None:
        """
        Test `_consumers_to_start` can be set and fetched correctly.

        Test that when we set consumers via the `_set_consumers_to_start` method that
        the `_consumers_to_start` attribute is set to the proper value.

        :param daq_component_manager: the daq receiver component manager
            under test.
        :param consumer_list: A comma separated list of consumers to start.
        """
        assert daq_component_manager._consumers_to_start == ""
        daq_component_manager._set_consumers_to_start(consumer_list)
        assert daq_component_manager._consumers_to_start == consumer_list