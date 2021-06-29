# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements infrastructure for mocking Tango.Group instances."""
from __future__ import annotations  # allow forward references in type hints

import unittest.mock

from tango import Group
from ska_low_mccs import MccsDeviceProxy

from testing.harness.mock import MockDeviceBuilder


__all__ = ["MockGroupBuilder"]


class MockGroupBuilder():
    """This module implements a mock builder for Tango.Group instances."""

    def __init__(
        self: MockGroupBuilder, from_factory: unittest.mock.Mock = unittest.mock.Mock
    ) -> None:
        """
        Create a new instance.

        :param from_factory: an optional factory from which to draw the
            original mock
        """
        super().__init__(from_factory=from_factory)
        self._devices = []

    def add(self, pattern_subgroup, timeout_ms=-1):
        pass

    def write_attribute_asynch(self, attr_name, value):
        pass
