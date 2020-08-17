"""
This module contains pytest fixtures and other test setups common to
all ska.low.mccs tests: unit, integration and functional (BDD)
"""


def pytest_addoption(parser):
    """
    Pytest hook; implemented to add the `--true-context` option, used to
    indicate that a true Tango subsystem is available, so there is no
    need for a MultiDeviceTestContext

    :param parser: the command line options parser
    :type parser: an argparse parser
    """
    parser.addoption(
        "--true-context",
        action="store_true",
        help=(
            "Tell pytest that you have a true Tango context and don't "
            "need to spin up a Tango test context"
        ),
    )
