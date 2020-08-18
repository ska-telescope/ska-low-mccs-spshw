"""
Module for MCCS utils
"""
from functools import wraps
import inspect
import threading
import pkg_resources
import json
import jsonschema

import tango
from tango import DevState
from tango import EventType, AttrQuality
from tango import Except, ErrSeverity
from tango.server import Device

from ska.base.control_model import HealthState


def tango_raise(
    msg, reason="API_CommandFailed", severity=ErrSeverity.ERR, _origin=None
):
    """Helper function to provide a concise way to throw `tango.Except.throw_exception`

    Example::

        class MyDevice(Device):
            @command
            def some_command(self):
                if condition:
                    pass
                else:
                    tango_throw("Condition not true")


    :param msg: [description]
    :type msg: [type]
    :param reason: the tango api DevError description string, defaults to
                     "API_CommandFailed"
    :type reason: str, optional
    :param severity: the tango error severity, defaults to `tango.ErrSeverity.ERR`
    :type severity: `tango.ErrSeverity`, optional
    :param _origin: the calling object name, defaults to None (autodetected)
                   Note that autodetection only works for class methods not e.g.
                   decorators
    :type _origin: str, optional
    """
    if _origin is None:
        frame = inspect.currentframe().f_back
        calling_method = frame.f_code.co_name
        calling_class = frame.f_locals["self"].__class__
        if Device not in inspect.getmro(calling_class):
            raise TypeError("Can only be used in a tango device instance")
        class_name = calling_class.__name__
        _origin = f"{class_name}.{calling_method}()"
    Except.throw_exception(reason, msg, _origin, severity)


def call_with_json(func, **kwargs):
    """
    Allows the calling of a command that accepts a JSON string as input,
    with the actual unserialised parameters.

    :param func: the function to call
    :ptype func: callable
    :param kwargs: parameters to be jsonified and passed to func
    :ptype kwargs: any
    :return: the return value of func
    :example: Suppose you need to use MccsMaster.Allocate() to command
        a master device to allocate certain stations and tiles to a
        subarray. Allocate() accepts a single JSON string argument.
        Instead of

            parameters={"id": id, "stations": stations, "tiles": tiles}
            json_string=json.dumps(parameters)
            master.Allocate(json_string)

        save yourself the trouble and

            call_with_json(master.Allocate,
                           id=id, stations=stations, tiles=tiles)

    """
    return func(json.dumps(kwargs))


class json_input:
    """
    Method decorator that parses and validates JSON input into a python
    object. The wrapped method is thus called with a JSON string, but
    can be implemented as if it had been passed an object.

    If the string cannot be parsed as JSON, an exception is raised.

    :param schema_path: an optional path to a schema against which the
        JSON should be validated. Not working at the moment, so leave it
        None.
    :ptype: string
    :raises FileNotFoundException: if no file is found at the schema
        path provided
    :raises json.JSONDecodeError: if the file at the specified schema
        path is not valid JSON

    :example: Conceptually, MccsMaster.Allocate() takes as arguments a
        subarray id, an array of stations, and an array of tiles. In
        practice, however, these arguments are encoded into a JSON
        string. Implement the function with its conceptual parameters,
        then wrap it in this decorator:

            @json_input
            def MccsMaster.Allocate(id, stations, tiles):

        The decorator will provide the JSON interface and handle the
        decoding for you.
    """

    def __init__(self, schema_path=None):
        """
        Initialises a callable json_input object, to function as a
        device method generator.
        """
        self.schema = None

        if schema_path is not None:
            schema_string = pkg_resources.resource_string(
                "ska.low.mccs.schemas", schema_path
            )
            self.schema = json.loads(schema_string)

    def __call__(self, func):
        """
        The decorator method. Makes this class callable, and ensures
        that when called on a device method, a wrapped method is
        returned.

        :param func: The target of the decorator
        :type func: function

        """

        @wraps(func)
        def wrapped(cls, json_string):
            json_object = self._parse(json_string, func.__name__)
            return func(cls, **json_object)

        return wrapped

    def _parse(self, json_string, origin):
        """
        Parses and validates the JSON string input.

        :param json_string: a string, purportedly a JSON-encoded object
        :type json_string: str
        :param origin: the origin of this check; used to construct a
            helpful DevFailed exception.
        :type origin: str
        :raises json.JSONDecodeError: if the string cannot be decoded as
            a JSON string
        :raises jsonschema.ValidationError: if the decoded JSON object
            does not validate against a schema

        """
        json_object = json.loads(json_string)

        if self.schema is not None:
            jsonschema.validate(json_object, self.schema)

        return json_object


class EventManager:
    def __init__(self, fqdn, update_callback=None):
        self._eventIds = []
        self._fqdn = fqdn
        self.callback = update_callback
        # Always subscribe to state change, it's pushed by the base classes
        self._event_names = ["state", "healthState", "localHealthState"]
        # stateless=True is needed to deal with device not running or device restart
        try:
            self._deviceProxy = tango.DeviceProxy(fqdn)
            for event_name in self._event_names:
                print(f"subscribing to {fqdn} {event_name}")
                id = self._deviceProxy.subscribe_event(
                    event_name, EventType.CHANGE_EVENT, self, stateless=True
                )
                self._eventIds.append(id)
        except tango.DevFailed as df:
            print(df)

    def unsubscribe(self):
        for eventId in self._eventIds:
            self._deviceProxy.unsubscribe_event(eventId)

    def push_event(self, ev):
        if ev.attr_value is not None and ev.attr_value.value is not None:
            print("----------------------------")
            print("Event @ ", ev.get_date())
            # print(self._deviceProxy.name())
            # print("in  push_event", ev.attr_value.name, ev.attr_value.value)
            # print(ev.attr_value.quality)
            if (
                ev.attr_value.quality == AttrQuality.ATTR_VALID
                and self.callback is not None
            ):
                self.callback(self._fqdn, ev.attr_value.name, ev.attr_value.value)


class HealthMonitor:
    """
    HealthMonitor is the health monitor for the MCCS prototype.
    """

    def __init__(self, device):
        """HealthMonitor constructor"""
        self._health_state_table = {}
        self._device = device
        self._lock = threading.Lock()

    def init_health_table(self, fqdns):
        """Initialise a table of State and Health with FQDN keys"""
        for fqdn in fqdns:
            self._health_state_table.update({fqdn: (DevState.OFF, HealthState.OK)})

    def update_health_table(self, fqdn, event, value):
        """
        Callback routine for Event Manager push events
        """
        state, health = self._health_state_table[fqdn]
        if fqdn != self._device.get_name():
            if event == "state":
                self._health_state_table.update({fqdn: (value, health)})
            elif event == "healthstate":
                self._health_state_table.update({fqdn: (state, HealthState(value))})
        else:
            if event == "state":
                self._health_state_table.update({fqdn: (value, health)})
            elif event == "localhealthstate":
                self._health_state_table.update({fqdn: (state, HealthState(value))})

        self.rollup_health()

    def rollup_health(self):
        """
        Rollup the health states of an element and its constituent sub-elements
        and push the resultant health state to the enclosing element.
        """
        health_state = HealthState.OK
        for key, (state, health) in self._health_state_table.items():
            if health == HealthState.DEGRADED or health == HealthState.UNKNOWN:
                health_state = HealthState.DEGRADED
            elif health == HealthState.FAILED:
                health_state = HealthState.FAILED
                break

        # print(self._health_state_table)
        self._device.push_change_event("healthState", health_state)
        with self._lock:
            self._device._health_state = health_state
        print("health state=", health_state)
