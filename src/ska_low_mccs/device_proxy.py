# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
"""This module implements a base device proxy for MCCS devices."""

from __future__ import annotations  # allow forward references in type hints

__all__ = ["MccsDeviceProxy"]

import logging
from typing import Any, Callable, Optional, Type
from typing_extensions import TypedDict
import warnings

import backoff
import tango
from tango import DevFailed, DevState, AttrQuality

# type for the "details" dictionary that backoff calls its callbacks with
BackoffDetailsType = TypedDict("BackoffDetailsType", {"args": list, "elapsed": float})
ConnectionFactory = Callable[[str], tango.DeviceProxy]


class MccsDeviceProxy:
    """
    This class implements a base device proxy for MCCS devices.

    At present it supports:

    * deferred connection: we can create the proxy without immediately
      trying to connect to the proxied device.
    * a :py:meth:``connect`` method, for establishing that connection
      later
    * a :py:meth:``check_initialised`` method, for checking that /
      waiting until the proxied device has transitioned out of INIT
      state.
    * Ability to subscribe to change events via the
      :py:meth:``add_change_event_callback`` method.
    """

    _default_connection_factory = tango.DeviceProxy

    @classmethod
    def set_default_connection_factory(
        cls: Type[MccsDeviceProxy], connection_factory: ConnectionFactory
    ) -> None:
        """
        Set the default connection factory for this class. This is super
        useful for unit testing: we can mock out
        :py:class:`tango.DeviceProxy` altogether, by simply setting this
        class's default connection factory to a mock factory.

        :param connection_factory: default factory to use to establish
            a connection to the device
        """
        cls._default_connection_factory = connection_factory

    def __init__(
        self: MccsDeviceProxy,
        fqdn: str,
        logger: logging.Logger,
        connect: bool = True,
        connection_factory: Optional[ConnectionFactory] = None,
        pass_through: bool = True,
    ) -> None:
        """
        Create a new instance.

        :param fqdn: fqdn of the device to be proxied
        :param logger: a logger for this proxy to use
        :param connection_factory: how we obtain a connection to the\
            device we are proxying. By default this is
            :py:class:`tango.DeviceProxy`, but occasionally this needs
            to be changed. For example, when testing against a
            :py:class:`test_context.MultiDeviceTestContext`, we
            obtain connections to the devices under test via
            ``test_context.get_device(fqdn)``.
        :param connect: whether to connect immediately to the device. If
            False, then the device may be connected later by calling the
            :py:meth:`.connect` method.
        :param pass_through: whether to pass unrecognised attribute
            accesses through to the underlying connection. Defaults to
            ``True`` but this will likely change in future once our
            proxies are more mature.
        """
        # Directly accessing object dictionary because we are overriding
        # setattr and don't want to infinitely recurse.
        self.__dict__["_fqdn"] = fqdn
        self.__dict__["_logger"] = logger
        self.__dict__["_connection_factory"] = (
            connection_factory or MccsDeviceProxy._default_connection_factory
        )
        self.__dict__["_pass_through"] = pass_through
        self.__dict__["_device"] = None

        self.__dict__["_change_event_subscription_ids"] = {}
        self.__dict__["_change_event_callbacks"] = {}

        if connect:
            self.connect()

    def connect(self: MccsDeviceProxy, max_time: float = 120.0) -> None:
        """
        Establish a connection to the device that we want to proxy.

        :param max_time: the maximum time, in seconds, to wait for a
            connection to be established. The default is 120 i.e. two
            minutes. If set to 0 or None, a single connection attempt is
            made, and the call returns immediately.
        """

        def _on_giveup_connect(details: BackoffDetailsType) -> None:
            """
            Give up trying to make a connection to the device.

            :param details: a dictionary providing call context, such as
                the call args and the elapsed time
            """
            fqdn = details["args"][1]
            elapsed = details["elapsed"]
            self._logger.warning(
                f"Gave up trying to connect to device {fqdn} after "
                f"{elapsed} seconds."
            )

        @backoff.on_exception(
            backoff.expo,
            DevFailed,
            on_giveup=_on_giveup_connect,
            factor=1,
            max_time=max_time,
        )
        def _backoff_connect(
            connection_factory: Callable[[str], tango.DeviceProxy], fqdn: str
        ) -> tango.DeviceProxy:
            """
            Attempt connection to a specified device.

            Connection attribute use an exponential backoff-retry
            scheme in case of failure.

            :param connection_factory: the factory to use to establish
                the connection
            :param fqdn: the fully qualified device name of the device

            :return: a proxy for the device
            """
            return _connect(connection_factory, fqdn)

        def _connect(
            connection_factory: Callable[[str], tango.DeviceProxy], fqdn: str
        ) -> tango.DeviceProxy:
            """
            Make a single attempt to connect to a device.

            :param connection_factory: the factory to use to establish
                the connection
            :param fqdn: the fully qualified device name of the device

            :return: a proxy for the device
            """
            return connection_factory(fqdn)

        if max_time:
            self._device = _backoff_connect(self._connection_factory, self._fqdn)
        else:
            self._device = _connect(self._connection_factory, self._fqdn)

    def check_initialised(self: MccsDeviceProxy, max_time: float = 120.0) -> bool:
        """
        Check that the device has completed initialisation.

        That is, check that the device is no longer in state INIT.

        :param max_time: the (optional) maximum time, in seconds, to
            wait for the device to complete initialisation. The default
            is 120.0 i.e. two minutes. If set to 0 or None, the device
            is checked once and the call returns immediately.

        :return: whether the device is initialised yet
        """

        def _on_giveup_check_initialised(details: BackoffDetailsType) -> None:
            """
            Give up waiting for the device to complete initialisation.

            :param details: a dictionary providing call context, such as
                the call args and the elapsed time
            """
            elapsed = details["elapsed"]
            self._logger.warning(
                f"Gave up waiting for the device ({self._fqdn}) to complete "
                f"initialisation after {elapsed} seconds."
            )

        @backoff.on_predicate(
            backoff.expo,
            on_giveup=_on_giveup_check_initialised,
            factor=1,
            max_time=max_time,
        )
        def _backoff_check_initialised(device: tango.DeviceProxy) -> bool:
            """
            Check that the device has completed initialisation.

            That is, check that the device is no longer in
            :py:const:`tango.DevState.INIT`. This check is performed
            in an exponential backoff-retry loop.

            :param device: the device to be checked

            :return: whether the device has completed initialisation
            """
            return _check_initialised(device)

        def _check_initialised(device: tango.DeviceProxy) -> bool:
            """
            Check that the device has completed initialisation.

            That is, check that the device is no longer in
            :py:const:`tango.DevState.INIT`.

            Checking that a device has initialised means calling its
            `state()` method, and even after the device returns a
            response from a ping, it might still raise an exception in
            response to reading device state
            (``"BAD_INV_ORDER_ORBHasShutdown``). So here we catch that
            exception.

            This method only performs a single check, and returns
            immediately. To check for initialisation in an exponential
            backoff-retry loop, use
            :py:meth:`._backoff_check_initialised`.

            :param device: the device to be checked

            :return: whether the device has completed initialisation
            """
            try:
                return device.state() != DevState.INIT
            except DevFailed:
                self._logger.debug(
                    "Caught a DevFailed exception while checking that the device has "
                    "initialised. This is most likely a 'BAD_INV_ORDER_ORBHasShutdown "
                    "exception triggered by the call to state()."
                )
                return False

        if max_time:
            return _backoff_check_initialised(self._device)
        else:
            return _check_initialised(self._device)

    def add_change_event_callback(
        self: MccsDeviceProxy,
        attribute_name: str,
        callback: Callable[[str, Any, AttrQuality], None],
    ) -> None:
        """
        Register a callback for change events being pushed by the device.

        :param attribute_name: the name of the attribute for which
            change events are subscribed.
        :param callback: the function to be called when a change event
            arrives.
        """
        attribute_key = attribute_name.lower()
        if attribute_key not in self._change_event_subscription_ids:
            self._change_event_callbacks[attribute_key] = [callback]
            self._change_event_subscription_ids[
                attribute_key
            ] = self._subscribe_change_event(attribute_name)
        else:
            self._change_event_callbacks[attribute_key].append(callback)
        self._call_callback(callback, self._read(attribute_name))

    @backoff.on_exception(backoff.expo, tango.DevFailed, factor=1, max_time=120)
    def _subscribe_change_event(self: MccsDeviceProxy, attribute_name: str) -> int:
        """
        Subscribe to a change event.

        Even though we already have a DeviceProxy to the device that we
        want to subscribe to, it is still possible that the device is
        not ready, in which case subscription will fail and a
        :py:class:`tango.DevFailed` exception will be raised. Here, we
        attempt subscription in a backoff-retry, and only raise the
        exception one our retries are exhausted. (The alternative option
        of subscribing with "stateless=True" could not be made to work.)

        :param attribute_name: the name of the attribute for which
            change events are subscribed

        :return: the subscription id
        """
        return self._device.subscribe_event(
            attribute_name, tango.EventType.CHANGE_EVENT, self._change_event_received
        )

    def _change_event_received(self: MccsDeviceProxy, event: tango.EventData) -> None:
        """
        Callback called by the tango system when a subscribed event occurs.

        It in turn invokes all its own callbacks.

        :param event: an object encapsulating the event data.
        """
        attribute_data = self._process_event(event)
        for callback in self._change_event_callbacks[attribute_data.name.lower()]:
            self._call_callback(callback, attribute_data)

    def _call_callback(
        self: MccsDeviceProxy,
        callback: Callable[[str, Any, AttrQuality], None],
        attribute_data: tango.DeviceAttribute,
    ) -> None:
        """
        Call the callback with unpacked attribute data.

        :param callback: function handle for the callback
        :param attribute_data: the attribute data to be unpacked and
            used to call the callback
        """
        callback(attribute_data.name, attribute_data.value, attribute_data.quality)

    def _process_event(
        self: MccsDeviceProxy, event: tango.EventData
    ) -> tango.DeviceAttribute:
        """
        Process a received event.

        Extract the attribute value from the event; or, if the event
        failed to carry an attribute value, read the attribute value
        directly.

        :param event: the received event

        :return: the attribute value data
        """
        if event.attr_value is None:
            warning_message = (
                "Received change event with empty value. Falling back to manual "
                f"attribute read. Event.err is {event.err}. Event.errors is\n"
                f"{event.errors}."
            )
            warnings.warn(UserWarning(warning_message))
            self._logger.warn(warning_message)
            return self._read(event.attr_name)
        else:
            return event.attr_value

    def _read(self: MccsDeviceProxy, attribute_name: str) -> Any:
        """
        Manually read an attribute.

        Used when we receive an event with empty attribute data.

        :param attribute_name: the name of the attribute to be read

        :return: the attribute value
        """
        return self._device.read_attribute(attribute_name)

    def __del__(self: MccsDeviceProxy) -> None:
        """Cleanup before destruction."""
        for subscription_id in self._change_event_subscription_ids:
            self._device.unsubscribe_event(subscription_id)

    def __setattr__(self: MccsDeviceProxy, name: str, value: Any) -> None:
        """
        Handler for setting attributes on this object.

        If the name matches an attribute that this object already has,
        we update it. But we refuse to create any new attributes.
        Instead, if we're in pass-through mode, we pass the setattr
        down to the underlying connection.

        :param name: the name of the attribute to be set
        :param value: the new value for the attribute

        :raises ConnectionError: if the device is not connected yet.
        """
        if name in self.__dict__:
            self.__dict__[name] = value
        elif self._pass_through:
            if self._device is None:
                raise ConnectionError("MccsDeviceProxy has not connected yet.")
            setattr(self._device, name, value)

    def __getattr__(self: MccsDeviceProxy, name: str, default_value: Any = None) -> Any:
        """
        Handler for any requested attribute not found in the usual way.

        If this proxy is in pass-through mode, then we try to get this
        attribute from the underlying proxy.

        :param name: name of the requested attribute
        :param default_value: value to return if the attribute is not
            found

        :raises AttributeError: if neither this class nor the underlying
            proxy (if in pass-through mode) has the attribute.

        :return: the requested attribute
        """
        if self._pass_through and self._device is not None:
            return getattr(self._device, name, default_value)
        elif default_value is not None:
            return default_value
        else:
            raise AttributeError(f"No such attribute: {name}")
