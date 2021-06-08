# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""
This subpackage contains modules that implement the MCCS Cluster
Manager, including a Tango device and a simulator.
"""


__all__ = ["MccsClusterManagerDevice", "cluster_manager_device"]

from .cluster_manager_device import MccsClusterManagerDevice
