# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Release information for SKA MCCS Python Package."""
import sys
from typing import Optional

name = "ska_low_mccs"
version = "0.9.0"
version_info = version.split(".")
description = "A set of Low MCCS tango devices for the SKA Telescope."
author = "Team MCCS"
author_email = "malte.marquarding at csiro dot au"
url = "https://www.skatelescope.org/"
license = "BSD-3-Clause"  # noqa: A001
copyright = "CSIRO and STFC Daresbury Laboratory \
    and University of Manchester"  # noqa: A001


def get_release_info(clsname: Optional[str] = None) -> str:
    """
    Return a formatted release info string.

    :param clsname: optional name of class to add to the info

    :return: str
    """
    rmod = sys.modules[__name__]
    info = ", ".join((rmod.name, rmod.version, rmod.description))  # type: ignore[attr-defined]
    if clsname is None:
        return info
    return ", ".join((clsname, info))


if __name__ == "__main__":
    print(version)
