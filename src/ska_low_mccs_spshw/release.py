# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Release information for SKA MCCS SPSHW Python Package."""
import os
import sys
from typing import Optional

name = "ska_low_mccs_spshw"
release_filename = os.path.join("..", "..", ".release")
with open(".release", encoding="utf8") as fd:
    line = fd.readline()
    version = line.strip().split("=")[1]
version_info = version.split(".")
description = (
    "A set of common code for Low MCCS SPSHW tango devices for the SKA Telescope."
)
author = "Team MCCS"
url = "https://www.skatelescope.org/"

# pylint: disable=redefined-builtin
license = "BSD-3-Clause"  # noqa: A001

# pylint: disable=redefined-builtin
copyright = (  # noqa: A001
    "CSIRO, INAF, I.T. Dev Ltd, Observatory Sciences Ltd"
    "Raman Research Institute, Science and Technology Facilities Council"
    "SKA Observatory, University of Malta, University of Manchester"
    "University of Oxford"
)


def get_release_info(clsname: Optional[str] = None) -> str:
    """
    Return a formatted release info string.

    :param clsname: optional name of class to add to the info

    :return: str
    """
    rmod = sys.modules[__name__]
    info = ", ".join(  # type: ignore[attr-defined]
        (rmod.name, rmod.version, rmod.description)
    )
    if clsname is None:
        return info
    return ", ".join((clsname, info))


if __name__ == "__main__":
    print(version)
