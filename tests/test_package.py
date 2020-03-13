from skamccs import release


def test_release():
    release_keys = ['author', 'author_email', 'copyright',
                    'description', 'license', 'name', 'url',
                    'version', 'version_info']
    assert set(dir(release)).issuperset(release_keys)
