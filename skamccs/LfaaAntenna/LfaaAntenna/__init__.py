# -*- coding: utf-8 -*-
#
# This file is part of the LfaaAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""LFAA Antenna Device Server

An implementation of the Antenna Device Server for the MCCS based upon architecture in SKA-TEL-LFAA-06000052-02.
"""

from . import release
from .LfaaAntenna import LfaaAntenna, main

__version__ = release.version
__version_info__ = release.version_info
__author__ = release.author
