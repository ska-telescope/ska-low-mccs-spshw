"""
This module contains pytest fixtures and other test setups common to all
ska_low_mccs tests: unit, integration and functional (BDD).
"""
import logging

import pytest
import tango

from testing.harness.tango_harness import MccsDeviceTestContext


def pytest_sessionstart(session):
    """
    Pytest hook; prints info about tango version.

    :param session: a pytest Session object
    :type session: :py:class:`pytest.Session`
    """
    print(tango.utils.info())


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a :py:class:`tango.test_context.MultiDeviceTestContext`.

    :param parser: the command line options parser
    :type parser: :py:class:`argparse.ArgumentParser`
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )


@pytest.fixture()
def tango_config():
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    :returns: tango configuration information: a dictionary with keys
        "process", "host" and "port".
    :rtype: dict
    """
    return {"process": True, "host": None, "port": 0}


@pytest.fixture()
def device_context(devices_to_load, tango_config, logger):
    """
    Creates and returns an :py:class:`.MccsDeviceTestContext` object.

    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dict
    :param tango_config: fixture that returns configuration information
        that specifies how the Tango system should be established and
        run.
    :type tango_config: dict
    :param logger: the logger to be used by this object.
    :type logger: :py:class:`logging.Logger`

    :yield: a tango testing context
    """
    with MccsDeviceTestContext(
        devices_to_load,
        logger,
        source=tango.DevSource.DEV,
        process=tango_config["process"],
        host=tango_config["host"],
        port=tango_config["port"],
    ) as context:
        yield context


@pytest.fixture(scope="session")
def logger():
    """
    Fixture that returns a default logger.

    :return: a logger
    :rtype logger: :py:class:`logging.Logger`
    """
    return logging.getLogger()
