# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""Test for release module."""
from ska_low_mccs import release


def test_release() -> None:
    """Test that all setup attributes have been set."""
    release_keys = [
        "author",
        "author_email",
        "copyright",
        "description",
        "license",
        "name",
        "url",
        "version",
        "version_info",
    ]
    assert set(dir(release)).issuperset(release_keys)
