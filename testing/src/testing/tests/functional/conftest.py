"""
This module contains pytest fixtures and other test setups for the
ska_low_mccs functional (BDD) tests.
"""
import socket

import pytest
import tango
from tango.test_context import get_host_ip

from ska_low_mccs import MccsDeviceProxy

from testing.tests.conftest import MccsDeviceTestContext, MccsTangoContext


def pytest_configure(config):
    """
    Register custom markers to avoid pytest warnings.

    :param config: the pytest config object
    :type config: :py:class:`pytest.config.Config`
    """
    config.addinivalue_line("markers", "XTP-1170: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1257: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1260: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1261: XRay BDD test marker")
    config.addinivalue_line("markers", "XTP-1473: XRay BDD test marker")


@pytest.fixture(scope="module")
def patch_device_proxy():
    """
    Fixture that provides a patcher that set up
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` to use a connection factory
    that wraps :py:class:`tango.DeviceProxy` with a workaround for a bug
    in :py:class:`tango.test_context.MultiDeviceTestContext`, then returns the host
    and port used by the patch.

    This is a factory; the patch won't be applied unless you actually
    call the fixture.

    :return: the callable patcher
    :rtype: callable
    """

    def patcher():
        """
        Callable returned by this parent fixture, which performs
        patching when called.

        :return: the host and port used by the patch
        :rtype: tuple
        """

        def _get_open_port():
            """
            Helper function that returns an available port on the local
            machine.

            Note the possibility of a race condition here. By the time the
            calling method tries to make use of this port, it might already
            have been taken by another process.

            :return: An open port
            :rtype: int
            """
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
            s.close()
            return port

        host = get_host_ip()
        port = _get_open_port()

        MccsDeviceProxy.set_default_connection_factory(
            lambda fqdn, *args, **kwargs: tango.DeviceProxy(
                f"tango://{host}:{port}/{fqdn}#dbase=no", *args, **kwargs
            ),
        )
        return (host, port)

    return patcher


@pytest.fixture(scope="module")
def tango_config(patch_device_proxy):
    """
    Fixture that returns configuration information that specified how
    the Tango system should be established and run.

    This implementation entures that :py:class:`tango.DeviceProxy` is
    monkeypatched as a workaround for a bug in
    :py:class:`tango.test_context.MultiDeviceTestContext`, then returns the host and
    port used by the patch.

    This is a factory; the config won't actually be provided until you
    call it.

    :param patch_device_proxy: a fixture that handles monkeypatching of
        :py:class:`tango.DeviceProxy` as a workaround for a bug in
        :py:class:`tango.test_context.MultiDeviceTestContext`, and returns the host
        and port used in the patch
    :type patch_device_proxy: tuple

    :return: a callable that sets up the config
    :rtype: callable
    """

    def _config():
        """
        Function returned by the parent fixture that sets up the tango
        config when called.

        :returns: tango configuration information: a dictionary with keys
            "process", "host" and "port".
        :rtype: dict
        """
        (host, port) = patch_device_proxy()
        return {"process": True, "host": host, "port": port}

    return _config


@pytest.fixture(scope="module")
def tango_context(request, devices_to_load, tango_config, logger):
    """
    Returns a Tango context. The Tango context returned depends upon
    whether or not pytest was invoked with the `--true-context` option.

    If no, then this returns a tango.test_context.MultiDeviceTestContext
    set up with the devices specified in the module's devices_info.

    If yes, then this returns a context with an interface like that of
    tango.test_context.MultiDeviceTestContext, but actually providing
    access to a true Tango context.

    :todo: Even when testing against a true Tango context, we are still
        setting up the test context. This will be fixed when we unify
        the test harnesses (MCCS-329)

    :param request: A pytest object giving access to the requesting test
        context.
    :type request: :py:class:`pytest.FixtureRequest`
    :param devices_to_load: fixture that provides a specification of the
        devices that are to be included in the devices_info dictionary
    :type devices_to_load: dict
    :param tango_config: fixture that returns configuration information
        that specifies how the Tango system should be established and
        run.
    :type tango_config: dict
    :param logger: the logger to be used by this object.
    :type logger: :py:class:`logging.Logger`

    :yield: a tango context
    """
    try:
        true_context = request.config.getoption("--true-context")
    except ValueError:
        true_context = False

    if true_context:
        with MccsTangoContext(
            devices_to_load,
            logger,
            source=tango.DevSource.DEV,
        ) as context:
            yield context
    else:
        config = tango_config()
        with MccsDeviceTestContext(
            devices_to_load,
            logger,
            source=tango.DevSource.DEV,
            process=config["process"],
            host=config["host"],
            port=config["port"],
        ) as context:
            yield context


@pytest.fixture(scope="module")
def cached_obsstate():
    """
    Use a pytest message box to retain obsstate between test stages.

    :return: cached_obsstate: pytest message box for the cached obsstate
    :rtype: cached_obsstate:
        dict<string, :py:class:`~ska_tango_base.control_model.ObsState`>
    """
    return {}
