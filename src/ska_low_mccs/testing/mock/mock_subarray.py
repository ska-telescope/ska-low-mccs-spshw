# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements infrastructure for mocking MCCS subarray devices."""
from __future__ import annotations  # allow forward references in type hints

import unittest.mock

# from ska_low_mccs import MccsSubarray
from ska_low_mccs.testing.mock import MockDeviceBuilder

# from ska_tango_base.commands import ResultCode


__all__ = ["MockSubarrayBuilder"]


class MockSubarrayBuilder(MockDeviceBuilder):
    """This module implements a mock builder for MCCS subarray devices."""

    def __init__(
        self: MockSubarrayBuilder,
        from_factory: type[unittest.mock.Mock] = unittest.mock.Mock,
    ) -> None:
        """
        Create a new instance.

        :param from_factory: an optional factory from which to draw the
            original mock
        """
        super().__init__(from_factory=from_factory)


#         for (command_name, succeeded_message) in [
#             ("On", "Subarray On command completed OK"),
#             ("Off", "Subarray Off command completed OK"),
#             ("AssignResources", "AssignResources command completed OK"),
#             ("ReleaseResources", "ReleaseResources command completed OK"),
#             (
#                 "ReleaseAllResources",
#                 "ReleaseAllResources command completed OK",
#             ),
#             (
#                 "Configure",
#                 MccsSubarray.ConfigureCommand.RESULT_MESSAGES[ResultCode.OK],
#             ),
#             (
#                 "Restart",
#                 MccsSubarray.ConfigureCommand.RESULT_MESSAGES[ResultCode.OK],
#             ),
#             (
#                 "SendTransientBuffer",
#                 MccsSubarray.SendTransientBufferCommand.RESULT_MESSAGES[ResultCode.OK],
#             ),
#         ]:
#             self._configuration[f"{command_name}.return_value"] = [
#                 [ResultCode.OK],
#                 [succeeded_message],
#             ]