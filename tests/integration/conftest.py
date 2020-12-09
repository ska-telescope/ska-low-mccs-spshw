"""
This module contains pytest fixtures and other test setups for the
ska.low.mccs lightweight integration tests.
"""


def pytest_itemcollected(item):
    """
    pytest hook implementation; add the "forked" custom mark to all
    tests that use the `device_context` fixture, causing them to be
    sandboxed in their own process.

    :param item: the collected test for which this hook is called
    :type item: a collected test
    """
    if "device_context" in item.fixturenames:
        item.add_marker("forked")
