# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the tests of the transient buffer."""
from __future__ import annotations

from typing import Any, Union

import pytest
from _pytest.fixtures import SubRequest

from ska_low_mccs.transient_buffer import TransientBuffer, TransientBufferComponentManager


class TestTransientBuffer:
    """
    Class for testing commands common to the transient buffer and its component manager.

    Because the transient buffer component manager passes commands down
    to the transient buffer, many commands are common. Here we test
    those common commands.
    """

    @pytest.fixture(
        params=["transient_buffer", "transient_buffer_component_manager",]
    )
    def transient_buffer(
        self: TestTransientBuffer,
        transient_buffer_component: TransientBuffer,
        transient_buffer_component_manager: TransientBufferComponentManager,
        request: SubRequest,
    ) -> Union[TransientBuffer, TransientBufferComponentManager]:
        """
        Return the transient buffer component class object under test.

        This is parametrised to return

        * a transient buffer,

        * a transient buffer component manager,

        So any test that relies on this fixture will be run twice.

        :param transient_buffer_component: the transient buffer to return
        :param transient_buffer_component_manager: the transient buffer
            component manager to return
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the tile class object under test
        """
        if request.param == "transient_buffer":
            return transient_buffer_component
        elif request.param == "transient_buffer_component_manager":
            transient_buffer_component_manager.start_communicating()
            return transient_buffer_component_manager
        raise ValueError("transient_buffer fixture parametrized with unrecognised option")

    @pytest.mark.parametrize(
        ("attribute_name", "expected_value"),
        (
            ("station_id", ""),
            ("transient_buffer_job_id", ""),
            ("resampling_bits", 0),
            ("n_stations", 0),
            ("transient_frequency_window", (0.0,)),
            ("station_ids", ["",],),
        ),
    )
    def test_read_attribute(
        self: TestTransientBuffer,
        transient_buffer: Union[TransientBuffer, TransientBufferComponentManager],
        attribute_name: str,
        expected_value: Any,
    ) -> None:
        """
        Tests that read-only attributes take certain known initial values.

        This is a weak test; over time we should find ways to more
        thoroughly test each of these independently.

        :param transient_buffer: the transient buffer class object under
            test.
        :param attribute_name: the name of the attribute under test
        :param expected_value: the expected value of the attribute. This
            can be any type, but the test of the attribute is a single
            "==" equality test.
        """
        assert getattr(transient_buffer, attribute_name) == expected_value
