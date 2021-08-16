"""This module contains the tests of the subarray beam component manager."""
from __future__ import annotations

import time
from typing import Any, Callable, Union

import pytest
from _pytest.fixtures import SubRequest

from ska_low_mccs.subarray_beam import (
    SubarrayBeam,
    SubarrayBeamComponentManager,
)

from ska_low_mccs.testing.mock import MockCallable


class TestSubarrayBeam:
    """
    Class for testing commands common to the subarray beam component and its component
    manager.

    Because the subarray beam component manager passes commands down to
    to the subarray beam component, many commands are common. Here we
    test those common commands.
    """

    @pytest.fixture(
        params=[
            "subarray_beam",
            "subarray_beam_component_manager",
        ]
    )
    def subarray_beam(
        self: TestSubarrayBeam,
        subarray_beam_component: SubarrayBeam,
        subarray_beam_component_manager: SubarrayBeamComponentManager,
        is_configured_changed_callback: Callable[[bool], None],
        request: SubRequest,
    ) -> Union[SubarrayBeam, SubarrayBeamComponentManager]:
        """
        Return the subarray beam component class object under test.

        This is parametrised to return

        * a subarray beam component,

        * a subarray beam component manager,

        So any test that relies on this fixture will be run twice.

        :param subarray_beam_component: the subarray beam component to return
        :param subarray_beam_component_manager: the subarray beam component
            component manager to return
        :param is_configured_changed_callback: a callback to be called
            when whether the subarray beam is configured changes
        :param request: A pytest object giving access to the requesting test
            context.

        :raises AssertionError: if parametrized with an unrecognised option

        :return: the tile class object under test
        """
        if request.param == "subarray_beam":
            subarray_beam_component.set_is_configured_changed_callback(
                is_configured_changed_callback
            )
            return subarray_beam_component

        elif request.param == "subarray_beam_component_manager":
            subarray_beam_component_manager.start_communicating()
            time.sleep(0.1)
            return subarray_beam_component_manager
        raise AssertionError(
            "subarray beam fixture parametrized with unrecognised option"
        )

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value", "write_value"),
        [
            ("subarray_id", 0, None),
            ("subarray_beam_id", 0, None),
            ("station_ids", [], [3, 4, 5, 6]),
            ("logical_beam_id", 0, None),
            ("update_rate", 0.0, None),
            ("is_beam_locked", False, None),
            ("channels", [], None),
            ("antenna_weights", [], None),
            ("phase_centre", [], None),
        ],
    )
    def test_attribute(
        self: TestSubarrayBeam,
        subarray_beam: Union[SubarrayBeam, SubarrayBeamComponentManager],
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

        :param subarray_beam: the subarray beam component class object under
            test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        :param write_value: the value to write to the attribute
        """
        assert getattr(subarray_beam, attribute_name) == expected_value

        if write_value is not None:
            setattr(subarray_beam, attribute_name, write_value)
            assert getattr(subarray_beam, attribute_name) == write_value

    def test_desired_pointing(
        self: TestSubarrayBeam,
        subarray_beam: Union[SubarrayBeam, SubarrayBeamComponentManager],
    ) -> None:
        """
        Test the desired pointing attribute.

        This is a weak test that simply check that the attribute's
        initial value is as expected, and that we can write a new value
        to it.

        :param subarray_beam: the subarray beam component class object under
            test.
        """
        assert subarray_beam.desired_pointing == []

        value_to_write = [1585619550.0, 192.85948, 2.0, 27.12825, 1.0]
        subarray_beam.desired_pointing = value_to_write
        assert subarray_beam.desired_pointing == pytest.approx(value_to_write)

    def test_configure(
        self: TestSubarrayBeam,
        subarray_beam: Union[SubarrayBeam, SubarrayBeamComponentManager],
        is_configured_changed_callback: MockCallable,
    ) -> None:
        """
        Test the configure method.

        :param subarray_beam: the subarray beam component class object
            under test.
        :param is_configured_changed_callback: a callback to be called
            when whether the subarray beam is configured changes
        """
        is_configured_changed_callback.assert_next_call(False)

        subarray_beam_id = 1
        station_ids = [1, 2]
        update_rate = 3.14
        channels = [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]]
        desired_pointing = [1585619550.0, 192.0, 2.0, 27.0, 1.0]
        antenna_weights = [1.0, 1.0, 1.0]
        phase_centre = [0.0, 0.0]

        subarray_beam.configure(
            subarray_beam_id,
            station_ids,
            update_rate,
            channels,
            desired_pointing,
            antenna_weights,
            phase_centre,
        )
        is_configured_changed_callback.assert_next_call(True)

        assert subarray_beam.subarray_beam_id == subarray_beam_id
        assert subarray_beam.station_ids == station_ids
        assert subarray_beam.update_rate == pytest.approx(update_rate)
        assert subarray_beam.channels == channels
        assert subarray_beam.desired_pointing == pytest.approx(desired_pointing)
        assert subarray_beam.antenna_weights == pytest.approx(antenna_weights)
        assert subarray_beam.phase_centre == pytest.approx(phase_centre)
