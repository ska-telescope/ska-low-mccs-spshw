########################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
########################################################################
"""
This module contains the tests for the ska.low.mccs.health module.
"""
import pytest

# from tango import DevState
from tango import AttrQuality

from ska.base.control_model import AdminMode, HealthState
from ska.low.mccs.events import EventManager
from ska.low.mccs.health import (
    DeviceHealthPolicy,
    DeviceHealthRollupPolicy,
    DeviceHealthMonitor,
    HealthMonitor,
    HealthModel,
    MutableHealthMonitor,
    MutableHealthModel,
)


@pytest.fixture()
def mock_factory(mocker):
    """
    Fixture that provides a mock factory for device proxy mocks. This
    default factory provides vanilla mocks, but this fixture can be
    overridden by test modules/classes to provide mocks with specified
    behaviours.

    :param mocker: the pytest `mocker` fixture is a wrapper around the
        `unittest.mock` package
    :type mocker: wrapper for :py:mod:`unittest.mock`

    :return: a factory for device proxy mocks
    :rtype: :py:class:`unittest.Mock` (the class itself, not an
        instance)
    """
    _values = {"healthState": HealthState.UNKNOWN, "adminMode": AdminMode.ONLINE}

    def _mock_attribute(name, *args, **kwargs):
        """
        Returns a mock of a :py:class:`tango.DeviceAttribute` instance,
        for a given attribute name.

        :param name: name of the attribute
        :type name: str
        :param args: positional args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type args: list
        :param kwargs: named args to the
            :py:meth:`tango.DeviceProxy.read_attribute` method patched
            by this mock factory
        :type kwargs: dict

        :return: a basic mock for a :py:class:`tango.DeviceAttribute`
            instance, with name, value and quality values
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.name = name
        mock.value = _values.get(name, "MockValue")
        mock.quality = "MockQuality"
        return mock

    def _mock_device():
        """
        Returns a mock for a :py:class:`tango.DeviceProxy` instance,
        with its :py:meth:`tango.DeviceProxy.read_attribute` method
        mocked to return :py:class:`tango.DeviceAttribute` mocks.

        :return: a basic mock for a :py:class:`tango.DeviceProxy`
            instance,
        :rtype: :py:class:`unittest.Mock`
        """
        mock = mocker.Mock()
        mock.read_attribute.side_effect = _mock_attribute
        return mock

    return _mock_device


class TestDeviceHealthPolicy:
    """
    This class contains the tests for the DeviceHealthPolicy class.

    (The DeviceHealthPolicy class implements a policy by which a
    supervising device evaluates the health of a subservient device, on
    the basis of its self-reported health state, and on its admin mode,
    which determines whether its health should be taken into account or
    ignored.)
    """

    @pytest.mark.parametrize(
        ("admin_mode", "health_state", "expected_health"),
        [
            (None, None, HealthState.UNKNOWN),
            (None, HealthState.UNKNOWN, HealthState.UNKNOWN),
            (None, HealthState.FAILED, HealthState.UNKNOWN),
            (None, HealthState.DEGRADED, HealthState.UNKNOWN),
            (None, HealthState.OK, HealthState.UNKNOWN),
            (AdminMode.NOT_FITTED, None, None),
            (AdminMode.NOT_FITTED, HealthState.UNKNOWN, None),
            (AdminMode.NOT_FITTED, HealthState.FAILED, None),
            (AdminMode.NOT_FITTED, HealthState.DEGRADED, None),
            (AdminMode.NOT_FITTED, HealthState.OK, None),
            (AdminMode.RESERVED, None, None),
            (AdminMode.RESERVED, HealthState.UNKNOWN, None),
            (AdminMode.RESERVED, HealthState.FAILED, None),
            (AdminMode.RESERVED, HealthState.DEGRADED, None),
            (AdminMode.RESERVED, HealthState.OK, None),
            (AdminMode.OFFLINE, None, None),
            (AdminMode.OFFLINE, HealthState.UNKNOWN, None),
            (AdminMode.OFFLINE, HealthState.FAILED, None),
            (AdminMode.OFFLINE, HealthState.DEGRADED, None),
            (AdminMode.OFFLINE, HealthState.OK, None),
            (AdminMode.MAINTENANCE, None, HealthState.UNKNOWN),
            (AdminMode.MAINTENANCE, HealthState.UNKNOWN, HealthState.UNKNOWN),
            (AdminMode.MAINTENANCE, HealthState.FAILED, HealthState.FAILED),
            (AdminMode.MAINTENANCE, HealthState.DEGRADED, HealthState.DEGRADED),
            (AdminMode.MAINTENANCE, HealthState.OK, HealthState.OK),
            (AdminMode.ONLINE, None, HealthState.UNKNOWN),
            (AdminMode.ONLINE, HealthState.UNKNOWN, HealthState.UNKNOWN),
            (AdminMode.ONLINE, HealthState.FAILED, HealthState.FAILED),
            (AdminMode.ONLINE, HealthState.DEGRADED, HealthState.DEGRADED),
            (AdminMode.ONLINE, HealthState.OK, HealthState.OK),
        ],
    )
    def test_policy(self, admin_mode, health_state, expected_health):
        """
        Test that this policy computes health as expected.

        :param admin_mode: the adminMode of the device
        :type admin_mode: AdminMode
        :param health_state: the reported healthState of the device
        :type health_state: HealthState
        :param expected_health: the expected value for health, as
            evaluated by the policy under test, or None if the policy
            should determine that the health state of the device should
            be ignored.
        :type expected_health:
            :py:class:`~ska.base.control_model.HealthState`
        """
        assert (
            DeviceHealthPolicy.compute_health(admin_mode, health_state)
            == expected_health
        )


class TestDeviceHealthRollupPolicy:
    """
    This class contains tests of the DeviceHealthRollupPolicy class.

    (The DeviceHealthRollupPolicy class implements a policy by which a
    device should determine its own health, on the basis of the health
    of its hardware (if any) and of the devices that it supervises (if
    any).
    """

    @pytest.mark.parametrize(
        ("hardware_health", "device_healths", "expected_health"),
        [
            (None, None, HealthState.OK),
            (None, [None, None], HealthState.OK),
            (None, [None, HealthState.UNKNOWN], HealthState.UNKNOWN),
            (None, [None, HealthState.FAILED], HealthState.DEGRADED),
            (None, [None, HealthState.OK], HealthState.OK),
            (None, [HealthState.FAILED, HealthState.OK], HealthState.DEGRADED),
            (HealthState.DEGRADED, None, HealthState.DEGRADED),
            (HealthState.DEGRADED, [None, None], HealthState.DEGRADED),
            (HealthState.DEGRADED, [None, HealthState.FAILED], HealthState.DEGRADED),
            (HealthState.DEGRADED, [None, HealthState.OK], HealthState.DEGRADED),
            (
                HealthState.DEGRADED,
                [HealthState.FAILED, HealthState.OK],
                HealthState.DEGRADED,
            ),
            (HealthState.OK, None, HealthState.OK),
            (HealthState.OK, [], HealthState.OK),
            (HealthState.OK, [HealthState.OK], HealthState.OK),
            (
                HealthState.OK,
                [HealthState.OK, HealthState.UNKNOWN, HealthState.DEGRADED],
                HealthState.UNKNOWN,
            ),
            (
                HealthState.OK,
                [HealthState.FAILED, HealthState.OK],
                HealthState.DEGRADED,
            ),
            (
                HealthState.OK,
                [HealthState.DEGRADED, HealthState.OK],
                HealthState.DEGRADED,
            ),
        ],
    )
    def test_policy(self, hardware_health, device_healths, expected_health):
        """
        Test that this policy computes health as expected.

        :param hardware_health: the health of the hardware managed under
            this policy, or None if no hardware is managed under this
            policy
        :type hardware_health: HealthState
        :param device_healths: the reported healthState values of the
            devices managed by this policy, or None if no devices are
            managed under this policy. If a list is provided, the
            elements must be health values, or None if the health of
            a given device should be ignored
        :type device_healths:
            list(:py:class:`~ska.base.control_model.HealthState`)
        :param expected_health: the expected value for health, as
            evaluated by the policy under test, or None if the policy
            should determine that the health state of the device should
            be ignored.
        :type expected_health:
            :py:class:`~ska.base.control_model.HealthState`
        """
        assert (
            DeviceHealthRollupPolicy().compute_health(hardware_health, device_healths)
            == expected_health
        )


class TestDeviceHealthMonitor:
    """
    This class contains the tests for the DeviceHealthMonitor class.

    (The DeviceHealthMonitor monitors the health of a single device.)
    """

    def test(self, mocker, mock_device_proxies, logger):
        """
        Test that a DeviceHealthMonitor registers a change in device
        health when the device emits relevant events.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        fqdn = "mock/mock/1"
        event_manager = EventManager(logger)
        mock_callback = mocker.Mock()
        _ = DeviceHealthMonitor(event_manager, fqdn, mock_callback)

        mock_callback.assert_called_once_with(HealthState.UNKNOWN)
        mock_callback.reset_mock()

        # This is an implementation-dependent hack by which we pretend that the
        # device is emitting events
        admin_mode_mock_event = mocker.Mock()
        admin_mode_mock_event.attr_value.name = "adminMode"
        admin_mode_mock_event.attr_value.value = AdminMode.ONLINE
        admin_mode_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        # push the event
        event_manager._handlers[fqdn]._handlers["adminMode"].push_event(
            admin_mode_mock_event
        )
        mock_callback.assert_not_called()

        health_state_mock_event = mocker.Mock()
        health_state_mock_event.attr_value.name = "healthState"
        health_state_mock_event.attr_value.value = HealthState.DEGRADED
        health_state_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        # push the event
        event_manager._handlers[fqdn]._handlers["healthState"].push_event(
            health_state_mock_event
        )
        mock_callback.assert_called_once_with(HealthState.DEGRADED)


class TestHealthMonitor:
    """
    This class contains tests of the HealthMonitor class.

    (The HealthMonitor class monitors the health of a collection of
    subservient devices.)
    """

    def test(self, mocker, mock_device_proxies, logger):
        """
        Test that a HealthMonitor registers changes in device health
        when devices emit relevant events.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        fqdns = ["mock/mock/1", "mock/mock/2"]
        event_manager = EventManager(logger)
        mock_callback = mocker.Mock()
        _ = HealthMonitor(fqdns, event_manager, mock_callback)

        posargs = [call[0] for call in mock_callback.call_args_list]
        assert set(posargs) == set((fqdn, HealthState.UNKNOWN) for fqdn in fqdns)

        # This is an implementation-dependent hack by which we pretend that the
        # device is emitting events
        admin_mode_mock_event = mocker.Mock()
        admin_mode_mock_event.attr_value.name = "adminMode"
        admin_mode_mock_event.attr_value.value = AdminMode.ONLINE
        admin_mode_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        mock_callback.reset_mock()
        for fqdn in fqdns:
            # push the event
            event_manager._handlers[fqdn]._handlers["adminMode"].push_event(
                admin_mode_mock_event
            )
            mock_callback.assert_not_called()

        health_state_mock_event = mocker.Mock()
        health_state_mock_event.attr_value.name = "healthState"
        health_state_mock_event.attr_value.value = HealthState.DEGRADED
        health_state_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        for fqdn in fqdns:
            # push the event
            mock_callback.reset_mock()
            event_manager._handlers[fqdn]._handlers["healthState"].push_event(
                health_state_mock_event
            )
            mock_callback.assert_called_once_with(fqdn, HealthState.DEGRADED)


class TestHealthModel:
    """
    This class contains tests of the HealthModel class.

    (The HealthModel class represents and manages the health of a
    device.)
    """

    @pytest.mark.parametrize(
        ("with_hardware", "with_devices"),
        [(False, False), (False, True), (True, False), (True, True)],
    )
    def test(self, with_hardware, with_devices, mocker, mock_device_proxies, logger):
        """
        Test that the health of a HealthModel changes with changes to
        hardware health and/or changes to the health of managed devices.

        :param with_hardware: whether the model manages hardware or not
        :type with_hardware: bool
        :param with_devices: whether the model manages devices or not
        :type with_devices: bool
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        hardware = mocker.Mock() if with_hardware else None
        fqdns = ["mock/mock/1", "mock/mock/2"] if with_devices else None
        event_manager = EventManager(logger)
        mock_callback = mocker.Mock()

        health_model = HealthModel(hardware, fqdns, event_manager, mock_callback)
        if with_hardware or with_devices:
            mock_callback.assert_called_with(HealthState.UNKNOWN)
        else:
            mock_callback.assert_called_with(HealthState.OK)
        mock_callback.reset_mock()

        if with_hardware:
            health_model._hardware_health_changed(HealthState.OK)

            if with_devices:
                mock_callback.assert_not_called()  # health is still UNKNOWN
            else:
                mock_callback.assert_called_once_with(HealthState.OK)

        if with_devices:
            health_model._device_health_changed("mock/mock/1", HealthState.OK)
            mock_callback.assert_not_called()  # health is still UNKNOWN

            health_model._device_health_changed("mock/mock/2", HealthState.OK)
            mock_callback.assert_called_once_with(HealthState.OK)


class TestMutableHealthMonitor:
    """
    This class contains tests of the MutableHealthMonitor class.

    (The MutableHealthMonitor class monitors the health of a mutable
    collection of subservient devices.)
    """

    def test(self, mocker, mock_device_proxies, logger):
        """
        Test that one can add and remove device, and a
        MutableHealthMonitor behaves as expected.

        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        fqdns = ["mock/mock/1", "mock/mock/2"]

        event_manager = EventManager(logger)
        mock_callback = mocker.Mock()
        mutable_health_monitor = MutableHealthMonitor(
            fqdns, event_manager, mock_callback
        )

        posargs = [call[0] for call in mock_callback.call_args_list]
        assert set(posargs) == set((fqdn, HealthState.UNKNOWN) for fqdn in fqdns)

        mock_callback.reset_mock()

        new_fqdn = "mock/mock/3"
        mutable_health_monitor.add_devices([new_fqdn])
        mock_callback.assert_called_once_with(new_fqdn, HealthState.UNKNOWN)
        mock_callback.reset_mock()

        # This is an implementation-dependent hack by which we pretend that the
        # device is emitting events
        admin_mode_mock_event = mocker.Mock()
        admin_mode_mock_event.attr_value.name = "adminMode"
        admin_mode_mock_event.attr_value.value = AdminMode.ONLINE
        admin_mode_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        mock_callback.reset_mock()
        for fqdn in fqdns:
            # push the event
            event_manager._handlers[fqdn]._handlers["adminMode"].push_event(
                admin_mode_mock_event
            )
            mock_callback.assert_not_called()

        health_state_mock_event = mocker.Mock()
        health_state_mock_event.attr_value.name = "healthState"
        health_state_mock_event.attr_value.value = HealthState.DEGRADED
        health_state_mock_event.attr_value.quality = AttrQuality.ATTR_VALID

        event_manager._handlers[new_fqdn]._handlers["adminMode"].push_event(
            admin_mode_mock_event
        )
        event_manager._handlers[new_fqdn]._handlers["healthState"].push_event(
            health_state_mock_event
        )

        mock_callback.assert_called_once_with(new_fqdn, HealthState.DEGRADED)


class TestMutableHealthModel:
    """
    This class contains tests of the MutableHealthModel class.

    (The MutableHealthModel class represents and manages the health of a
    device for which subservient devices may change.)
    """

    @pytest.mark.parametrize("with_hardware", [False, True])
    def test(self, with_hardware, mocker, mock_device_proxies, logger):
        """
        Test that the health of a MutableHealthModel changes with
        changes to the collection of managed devices.

        :param with_hardware: whether the model manages hardware or not
        :type with_hardware: bool
        :param mocker: fixture that wraps unittest.Mock
        :type mocker: wrapper for :py:mod:`unittest.mock`
        :param mock_device_proxies: fixture that patches
            :py:class:`tango.DeviceProxy` to always return the same mock
            for each fqdn
        :type mock_device_proxies: dict (but don't access it directly,
            access it through :py:class:`tango.DeviceProxy` calls)
        :param logger: the logger to be used by the object under test
        :type logger: :py:class:`logging.Logger`
        """
        hardware = mocker.Mock() if with_hardware else None
        fqdns = ["mock/mock/1", "mock/mock/2"]
        event_manager = EventManager(logger)
        mock_callback = mocker.Mock()

        health_model = MutableHealthModel(hardware, fqdns, event_manager, mock_callback)
        mock_callback.assert_called_with(HealthState.UNKNOWN)
        mock_callback.reset_mock()

        if with_hardware:
            health_model._hardware_health_changed(HealthState.OK)
            mock_callback.assert_not_called()  # health is still UNKNOWN

        health_model._device_health_changed("mock/mock/1", HealthState.OK)
        mock_callback.assert_not_called()  # health is still UNKNOWN

        health_model._device_health_changed("mock/mock/2", HealthState.OK)
        mock_callback.assert_called_once_with(HealthState.OK)
        mock_callback.reset_mock()

        health_model.add_devices(["mock/mock/3"])
        mock_callback.assert_called_once_with(HealthState.UNKNOWN)
        mock_callback.reset_mock()

        health_model._device_health_changed("mock/mock/3", HealthState.DEGRADED)
        mock_callback.assert_called_once_with(HealthState.DEGRADED)
