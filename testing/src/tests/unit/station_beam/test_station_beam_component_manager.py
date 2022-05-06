# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the station beam component manager."""
from __future__ import annotations

import json
from typing import Any
import time

import pytest
from ska_tango_base.control_model import CommunicationStatus

from ska_low_mccs.station_beam import StationBeamComponentManager
from ska_low_mccs.testing.mock import MockCallable
from ska_tango_base.executor import TaskStatus


class TestStationBeamComponentManager:
    """Class for testing the station beam component manager."""

    def test_communication(
        self: TestStationBeamComponentManager,
        station_beam_component_manager: StationBeamComponentManager,
        communication_status_changed_callback: MockCallable,
        mock_station_off_fqdn: str,
        mock_station_on_fqdn: str,
    ) -> None:
        """
        Test the component manager's establishment of communication with its component.

        (i.e. its station)

        :param station_beam_component_manager: the station beam
            component manager under test.
        :param communication_status_changed_callback: callback to be
            called when the status of the communications channel between
            the component manager and its component changes
        :param mock_station_off_fqdn: the FQDN of a mock station in OFF
            state.
        :param mock_station_on_fqdn: the FQDN of a mock station in ON
            state.
        """
        station_beam_component_manager.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_beam_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        station_beam_component_manager.station_fqdn = mock_station_off_fqdn
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_beam_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        station_beam_component_manager.station_fqdn = mock_station_on_fqdn
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_beam_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

        station_beam_component_manager.station_fqdn = None
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
        assert (
            station_beam_component_manager.communication_status
            == CommunicationStatus.ESTABLISHED
        )

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value", "write_value"),
        [
            ("subarray_id", 0, None),
            ("station_id", 0, None),
            ("logical_beam_id", 0, None),
            ("update_rate", 0.0, None),
            ("is_beam_locked", False, None),
            ("channels", [], None),
            ("antenna_weights", [], None),
            ("pointing_delay", [], None),
            ("pointing_delay_rate", [], None),
            ("phase_centre", [], None),
        ],
    )
    def test_attribute(
        self: TestStationBeamComponentManager,
        station_beam_component_manager: StationBeamComponentManager,
        attribute_name: str,
        expected_value: Any,
        write_value: Any,
    ) -> None:
        """
        Test read-write attributes.

        Test that the attributes take certain known initial values, and
        that we can write new values if the attribute is writable.

        This is a weak test; over time we should find ways to more
        thoroughly test each of these independently.

        :param station_beam_component_manager: the station beam
            component manager under test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :param write_value: the value to write to the attribute
        """
        assert getattr(station_beam_component_manager, attribute_name) == expected_value

        if write_value is not None:
            setattr(station_beam_component_manager, attribute_name, write_value)
            assert (
                getattr(station_beam_component_manager, attribute_name) == write_value
            )

    def test_beam_id(
        self: TestStationBeamComponentManager,
        station_beam_component_manager: StationBeamComponentManager,
        beam_id: int,
    ) -> None:
        """
        Test read-beam id attributes.

        This is a weak test that simply tests that the beam id is what
        it was initialised with.

        :param station_beam_component_manager: the station beam component class object under
            test.
        :param beam_id: the beam id of the station beam
        """
        assert station_beam_component_manager.beam_id == beam_id

    def test_desired_pointing(
        self: TestStationBeamComponentManager,
        station_beam_component_manager: StationBeamComponentManager,
    ) -> None:
        """
        Test the desired pointing attribute.

        This is a weak test that simply check that the attribute's
        initial value is as expected, and that we can write a new value
        to it.

        :param station_beam_component_manager: the station beam component class object under
            test.
        """
        assert station_beam_component_manager.desired_pointing == []

        value_to_write = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        station_beam_component_manager.desired_pointing = value_to_write
        assert station_beam_component_manager.desired_pointing == pytest.approx(
            value_to_write
        )

    def test_configure(
        self: TestStationBeamComponentManager,
        station_beam_component_manager: StationBeamComponentManager,
    ) -> None:
        """
        Test the configure method.

        :param station_beam_component_manager: the station beam component class object under
            test.
        """
        station_beam_component_manager.start_communicating()
        assert station_beam_component_manager.communication_status == CommunicationStatus.ESTABLISHED
        station_beam_component_manager.on()
        #assert station_beam_component_manager.power_state == PowerState.ON

        beam_id = 2
        station_id = 1
        update_rate = 3.14
        channels = [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]]
        desired_pointing = [1585619550.0, 192.0, 2.0, 27.0, 1.0]
        antenna_weights = [1.0, 1.0, 1.0]
        phase_centre = [0.0, 0.0]

        config = {
            "beam_id": beam_id,
            "station_ids": [station_id],
            "update_rate": update_rate,
            "channels": [channels],
            "desired_pointing": [desired_pointing],
            "antenna_weights": [antenna_weights],
            "phase_centre": [phase_centre],
        }

        config_dict = json.dumps(config)

        # Queueing of configure works fine but _configure is never executed.
        # This test passes if _configure is called directly.
        # Probably failing due to comms/power states.
        task_status, response = station_beam_component_manager.configure(config_dict)
        assert task_status == TaskStatus.QUEUED
        assert response == "Task queued"
        time.sleep(0.1)

        # Not getting into _configure where the following are set.
        assert station_beam_component_manager.beam_id == beam_id
        assert station_beam_component_manager.station_id == station_id
        assert station_beam_component_manager.update_rate == pytest.approx(update_rate)
        assert station_beam_component_manager.channels == channels
        assert station_beam_component_manager.desired_pointing == pytest.approx(
            desired_pointing
        )
        assert station_beam_component_manager.antenna_weights == pytest.approx(
            antenna_weights
        )
        assert station_beam_component_manager.phase_centre == pytest.approx(
            phase_centre
        )
