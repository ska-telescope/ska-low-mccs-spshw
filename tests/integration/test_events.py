###############################################################################
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.
###############################################################################
"""
This test module contains tests of the Tango events subsystem. This
is external to the MCCS system, so this test module should eventually
be transferred to pytango itself (which currently contains no such
test.)
"""

import pytest
import threading

import tango
from tango.server import attribute, command, device_property, Device

from ska.low.mccs.utils import backoff_connect
from conftest import confirm_initialised


class ToggleDevice(Device):
    """
    A simple device that can be made to produce a change event on
    demand, for testing event handling
    """

    def init_device(self):
        """
        initialisation hook for this Tango device
        """
        self._is_toggled = False
        self.set_change_event("isToggled", True, False)
        self.set_state(tango.DevState.ON)

    @attribute(dtype=bool)
    def isToggled(self):
        """
        returns whether this device is toggled or not

        :return: whether this device is toggled or not
        :rtype: bool
        """
        return self._is_toggled

    @command()
    def Toggle(self):
        """
        Toggle the boolean value of the meaningless "value" attribute
        """
        self._is_toggled = not self._is_toggled
        self.push_change_event("isToggled", self._is_toggled)


class ClientDevice(Device):
    """
    A simple tango device that subscribes to another device and consumes
    its change events
    """

    fqdn = device_property(dtype=str)

    def init_device(self):
        """
        initialisation hook for this tango device
        """
        self.set_state(tango.DevState.INIT)

        self.get_device_properties()

        self._is_server_toggled = None

        self._thread = threading.Thread(target=self._connect_and_subscribe)
        self._thread.start()

    def _connect_and_subscribe(self):
        """
        Thread target for asynchronous initialisation of connections
        to external entities such as hardware and other devices.
        """
        with tango.EnsureOmniThread():
            self._device = backoff_connect(self.fqdn)

            self._subscription_id = self._device.subscribe_event(
                "isToggled", tango.EventType.CHANGE_EVENT, self
            )
            self.set_state(tango.DevState.ON)

    @attribute(dtype=bool)
    def isServerToggled(self):
        """
        Tango attribute that returns the whether or not its server is
        toggled

        :return: whether or not this client device's server device is
            toggled
        :rtype: bool
        """
        return self._is_server_toggled

    def push_event(self, event):
        """
        Callback hook for subscribed event

        :param event: the received event
        :type event: :py:class:`tango.EventType`
        """
        self._is_server_toggled = event.attr_value.value


@pytest.fixture()
def devices_info():
    """
    Fixture that overrules the usual devices_info fixture with a fixed
    devices_info dict

    :return: a devices_info dict for passing to a
        :py:class:`tango.test_context.MultiDeviceTestContext`
    :rtype: dict
    """
    return [
        {
            "class": ToggleDevice,
            "devices": ({"name": "test/toggle/1", "properties": {}},),
        },
        {
            "class": ClientDevice,
            "devices": (
                {"name": "test/client/1", "properties": {"fqdn": "test/toggle/1"}},
            ),
        },
    ]


# @pytest.mark.skip(reason="Faffing around")
def test(device_context):
    """
    Test that events are received

    :param device_context: fixture that provides a tango context of some
        sort
    :type device_context: a tango context of some sort; possibly a
        MultiDeviceTestContext, possibly the real thing. The only
        requirement is that it provide a "get_device(fqdn)" method that
        returns a DeviceProxy.
    """
    toggle_device = device_context.get_device("test/toggle/1")
    client_device = device_context.get_device("test/client/1")

    confirm_initialised([toggle_device, client_device])

    assert not client_device.isServerToggled

    toggle_device.Toggle()

    assert client_device.isServerToggled
