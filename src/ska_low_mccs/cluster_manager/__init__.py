# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This subpackage implements cluster manager functionality for MCCS.

It includes a cluster manager Tango device and a simulator.
"""


__all__ = ["MccsClusterManagerDevice", "cluster_manager_device"]

from .cluster_manager_device import MccsClusterManagerDevice  # type: ignore[attr-defined]
