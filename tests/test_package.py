"""Test for release module"""
from ska.mccs import release


def test_release():
    """Test that all setup attributes have been set"""
    release_keys = ['AUTHOR', 'AUTHOR_EMAIL', 'COPYRIGHT',
                    'DESCRIPTION', 'LICENSE', 'NAME', 'URL',
                    'VERSION', 'VERSION_INFO']
    assert set(dir(release)).issuperset(release_keys)
