# type: ignore
"""This module contains pytest-specific test harness for MCCS integration tests."""


def pytest_itemcollected(item):
    """
    Modify a test after it has been collected by pytest.

    This hook implementation adds the "forked" custom mark to all tests
    that use the `tango_harness` fixture, causing them to be sandboxed
    in their own process.

    :param item: the collected test for which this hook is called
    :type item: :py:class:`pytest.Item`
    """
    if "tango_harness" in item.fixturenames:
        item.add_marker("forked")
