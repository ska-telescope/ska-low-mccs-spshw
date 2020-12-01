# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
"""
Release information for SKA MCCS Python Package.
"""
import sys

name = """ska.low.mccs"""
version = "0.3.0"
version_info = version.split(".")
description = """A set of Low MCCS tango devices for the SKA Telescope."""
author = "Team MCCS"
author_email = "malte.marquarding at csiro dot au"
url = """https://www.skatelescope.org/"""
license = """BSD-3-Clause"""  # noqa: A001
copyright = (  # noqa: A001
    "CSIRO and STFC Daresbury Laboratory and University of Manchester"
)


def get_release_info(clsname=None):
    """
    Return a formatted release info string.

    :param clsname: optional name of class to add to the info
    :type clsname: str

    :return: str
    """
    rmod = sys.modules[__name__]
    info = ", ".join((rmod.name, rmod.version, rmod.description))
    if clsname is None:
        return info
    return ", ".join((clsname, info))


if __name__ == "__main__":
    print(version)
