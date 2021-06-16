# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements infrastructure for mocking MCCS subarray devices."""
from __future__ import annotations  # allow forward references in type hints

import unittest.mock

from ska_tango_base.commands import ResultCode

from ska_low_mccs import MccsSubarray

from testing.harness.mock import MockDeviceBuilder


__all__ = ["MockSubarrayBuilder"]


class MockSubarrayBuilder(MockDeviceBuilder):
    """This module implements a mock builder for MCCS subarray devices."""

    def __init__(
        self: MockSubarrayBuilder, from_factory: unittest.mock.Mock = unittest.mock.Mock
    ) -> None:
        """
        Create a new instance.

        :param from_factory: an optional factory from which to draw the
            original mock
        """
        super().__init__(from_factory=from_factory)

        for (command_name, command_class) in [
            ("On", MccsSubarray.OnCommand),
            ("Off", MccsSubarray.OffCommand),
            ("AssignResources", MccsSubarray.AssignResourcesCommand),
            ("ReleaseResources", MccsSubarray.ReleaseResourcesCommand),
            ("ReleaseAllResources", MccsSubarray.ReleaseAllResourcesCommand),
            ("Configure", MccsSubarray.ConfigureCommand),
        ]:
            self._configuration[f"{command_name}.return_value"] = [
                [ResultCode.OK],
                [command_class.SUCCEEDED_MESSAGE],
            ]
