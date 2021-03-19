"""
Test for release module.
"""
from ska_low_mccs import release


def test_release():
    """
    Test that all setup attributes have been set.
    """
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
