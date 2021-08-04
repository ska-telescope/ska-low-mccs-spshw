# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
"""Release information for SKA MCCS Python Package."""
import sys
from typing import Optional


name = "ska_low_mccs"
version = "0.8.4"
version_info = version.split(".")
description = "A set of Low MCCS tango devices for the SKA Telescope."
author = "Team MCCS"
author_email = "malte.marquarding at csiro dot au"
url = "https://www.skatelescope.org/"
license = "BSD-3-Clause"  # noqa: A001
copyright = (  # noqa: A001
    "CSIRO and STFC Daresbury Laboratory and University of Manchester"
)


def get_release_info(clsname: Optional[str] = None) -> str:
    """
    Return a formatted release info string.

    :param clsname: optional name of class to add to the info
    :type clsname: str

    :return: str
    """
    rmod = sys.modules[__name__]
    info = ", ".join(
        (rmod.name, rmod.version, rmod.description)  # type: ignore[attr-defined]
    )
    if clsname is None:
        return info
    return ", ".join((clsname, info))


if __name__ == "__main__":
    print(version)
