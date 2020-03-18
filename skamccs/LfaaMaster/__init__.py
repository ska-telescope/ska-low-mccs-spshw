# -*- coding: utf-8 -*-
#
# This file is part of the LfaaMaster project
#

"""LfaaMaster Tango device prototype

LfaaMaster TANGO device class for the LfaaMaster prototype
"""

from skamccs import release
from .LfaaMaster import LfaaMaster

__all__ = ["LfaaMaster"]
__version__ = release.version
__version_info__ = release.version_info
__author__ = release.author
