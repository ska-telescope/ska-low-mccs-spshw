# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module implements infrastructure for mocking callbacks and other callables."""
from __future__ import annotations
import collections  # allow forward references in type hints

import queue
import unittest.mock
from typing import Any, Optional, Sequence, Tuple

import tango

__all__ = ["MockCallable", "MockChangeEventCallback", "MockCallableDeque"]


class MockCallable:
    """
    This class implements a mock callable.

    It is useful for when you want to assert that a callable is called,
    but the callback is called asynchronously, so that you might have to
    wait a short time for the call to occur.

    If you use a regular mock for the callback, your tests will end up
    littered with sleeps:

    .. code-block:: python

        antenna_apiu_proxy.start_communicating()
        communication_status_changed_callback.assert_called_once_with(
            CommunicationStatus.NOT_ESTABLISHED
        )
        time.sleep(0.1)
        communication_status_changed_callback.assert_called_once_with(
            CommunicationStatus.ESTABLISHED
        )

    These sleeps waste time, slow down the tests, and they are difficult
    to tune: maybe you only need to sleep 0.1 seconds on your
    development machine, but what if the CI pipeline deploys the tests
    to an environment that needs 0.2 seconds for this?

    This class solves that by putting each call to the callback onto a
    queue. Then, each time we assert that a callback was called, we get
    a call from the queue, waiting if necessary for the call to arrive,
    but with a timeout:

    .. code-block:: python

        antenna_apiu_proxy.start_communicating()
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.NOT_ESTABLISHED
        )
        communication_status_changed_callback.assert_next_call(
            CommunicationStatus.ESTABLISHED
        )
    """

    def __init__(
        self: MockCallable,
        return_value: Any = None,
        called_timeout: float = 5.0,
        not_called_timeout: float = 1.0,
    ):
        """
        Initialise a new instance.

        :param return_value: what to return when called
        :param called_timeout: how long to wait for a call to occur when
            we are expecting one. It makes sense to wait a long time for
            the expected call, as it will generally arrive much much
            sooner anyhow, and failure for the call to arrive in time
            will cause the assertion to fail. The default is 5 seconds.
        :param not_called_timeout: how long to wait for a callback when
            we are *not* expecting one. Since we need to wait the full
            timeout period in order to determine that a callback has not
            arrived, asserting that a call has not been made can
            severely slow down your tests. By keeping this timeout quite
            short, we can speed up our tests, at the risk of prematurely
            passing an assertion. The default is 0.5
        """
        self._return_value: Any = return_value
        self._called_timeout = called_timeout
        self._not_called_timeout = not_called_timeout
        self._queue: queue.SimpleQueue = queue.SimpleQueue()

    def __call__(self: MockCallable, *args: Any, **kwargs: Any) -> Any:
        """
        Handle a callback call.

        Create a standard mock, call it, and put it on the queue. (This
        approach lets us take advantange of the mock's assertion
        functionality later.)

        :param args: positional args in the call
        :param kwargs: keyword args in the call

        :return: the object's return calue
        """
        called_mock = unittest.mock.Mock()
        called_mock(*args, **kwargs)
        self._queue.put(called_mock)
        return self._return_value

    def _fetch_call(self: MockCallable, timeout: float) -> Optional[unittest.mock.Mock]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def assert_not_called(self: MockCallable, timeout: Optional[float] = None) -> None:
        """
        Assert that the callback still has not been called after the timeout period.

        This is a slow method because it has to wait the full timeout
        period in order to determine that the call is not coming. An
        optional timeout parameter is provided for the situation where
        you are happy for the assertion to pass after a shorter wait
        time.

        :param timeout: optional timeout for the check. If not provided, the
            default is the class setting
        """
        timeout = self._not_called_timeout if timeout is None else timeout
        called_mock = self._fetch_call(timeout)
        if called_mock is None:
            return
        called_mock.assert_not_called()  # we know this will fail and raise an exception

    def assert_next_call(self: MockCallable, *args: Any, **kwargs: Any) -> None:
        """
        Assert the arguments of the next call to this mock callback.

        If the call has not been made, this method will wait up to the
        specified timeout for a call to arrive.

        :param args: positional args that the call is asserted to have
        :param kwargs: keyword args that the call is asserted to have

        :raises AssertionError: if the callback has not been called.
        """
        called_mock = self._fetch_call(self._called_timeout)
        assert called_mock is not None, "Callback has not been called."
        called_mock.assert_called_once_with(*args, **kwargs)

    def get_next_call(
        self: MockCallable,
    ) -> Tuple[Sequence[Any], Sequence[Any]]:
        """
        Return the arguments of the next call to this mock callback.

        This is useful for situations where you do not know exactly what
        the arguments of the next call will be, so you cannot use the
        :py:meth:`.assert_next_call` method. Instead you want to assert
        some specific properties on the arguments:

        .. code-block:: python

            (args, kwargs) = mock_callback.get_next_call()
            event_data = args[0].attr_value
            assert event_data.name == "healthState"
            assert event_data.value == HealthState.UNKNOWN
            assert event_data.quality == tango.AttrQuality.ATTR_VALID

        If the call has not been made, this method will wait up to the
        specified timeout for a call to arrive.

        :raises AssertionError: if the callback has not been called
        :return: an (args, kwargs) tuple
        """
        called_mock = self._fetch_call(self._called_timeout)
        assert called_mock is not None, "Callback has not been called."
        return called_mock.call_args

    def assert_last_call(self: MockCallable, *args: Any, **kwargs: Any) -> None:
        """
        Assert the arguments of the last call to this mock callback.

        The "last" call is the last call before an attempt to get the
        next event times out.

        This is useful for situations where we know a device may call a
        callback several time, and we don't care too much about the
        exact order of calls, but we do know what the final call should
        be.

        :param args: positional args that the call is asserted to have
        :param kwargs: keyword args that the call is asserted to have

        :raises AssertionError: if the callback has not been called.
        """
        called_mock = None
        while True:
            next_called_mock = self._fetch_call(self._not_called_timeout)
            if next_called_mock is None:
                break
            called_mock = next_called_mock
        assert called_mock is not None, "Callback has not been called."
        called_mock.assert_called_once_with(*args, **kwargs)


class MockChangeEventCallback(MockCallable):
    """
    This class implements a mock change event callback.

    It is a special case of a :py:class:`MockCallable` where the
    callable expects to be called with event_name, event_value and
    event_quality arguments (which is how
    :py:class:`ska_low_mccs.device_proxy.MccsDeviceProxy` calls its change event
    callbacks).
    """

    def __init__(
        self: MockChangeEventCallback,
        event_name: str,
        called_timeout: float = 5.0,
        not_called_timeout: float = 0.5,
        filter_for_change: bool = False,
    ):
        """
        Initialise a new instance.

        :param event_name: the name of the event for which this callable
            is a callback
        :param called_timeout: how long to wait for a call to occur when
            we are expecting one. It makes sense to wait a long time for
            the expected call, as it will generally arrive much much
            sooner anyhow, and failure for the call to arrive in time
            will cause the assertion to fail. The default is 5 seconds.
        :param not_called_timeout: how long to wait for a callback when
            we are *not* expecting one. Since we need to wait the full
            timeout period in order to determine that a callback has not
            arrived, asserting that a call has not been made can
            severely slow down your tests. By keeping this timeout quite
            short, we can speed up our tests, at the risk of prematurely
            passing an assertion. The default is 0.5
        :param filter_for_change: filtered?
        """
        self._event_name = event_name.lower()
        self._filter_for_change = filter_for_change
        self._previous_value = None

        super().__init__(None, called_timeout, not_called_timeout)

    def _fetch_change_event(
        self: MockChangeEventCallback, timeout: float
    ) -> None | tuple[str, Any, tango.AttrQuality]:
        while True:
            called_mock = self._fetch_call(timeout)
            if called_mock is None:
                return called_mock

            (args, kwargs) = called_mock.call_args
            assert len(args) == 1
            assert not kwargs

            event = args[0]
            assert (
                not event.err
            ), f"Received failed change event: error stack is {event.errors}."

            attribute_data = event.attr_value

            if self._filter_for_change and attribute_data.value == self._previous_value:
                continue

            self._previous_value = attribute_data.value
            return (attribute_data.name, attribute_data.value, attribute_data.quality)

    def get_next_change_event(self: MockChangeEventCallback) -> Any:
        """
        Return the attribute value in the next call to this mock change event callback.

        This is useful for situations where you do not know exactly what
        the value will be, so you cannot use the
        :py:meth:`.assert_next_change_event` method. Instead you want to
        assert some specific properties on the arguments.

        :raises AssertionError: if the callback has not been called
        :return: an (args, kwargs) tuple
        """
        call_data = self._fetch_change_event(self._called_timeout)
        assert call_data is not None, "Change event callback has not been called"
        (call_name, call_value, _) = call_data
        assert (
            call_name.lower() == self._event_name
        ), f"Event name '{call_name.lower()}'' does not match expected name '{self._event_name}'"
        return call_value

    def assert_next_change_event(
        self: MockChangeEventCallback,
        value: Any,
        quality: tango.AttrQuality = tango.AttrQuality.ATTR_VALID,
    ) -> None:
        """
        Assert the arguments of the next call to this mock callback.

        If the call has not been made, this method will wait up to the
        specified timeout for a call to arrive.

        :param value: the asserted value of the change event
        :param quality: the asserted quality of the change event. This
            is optional, with a default of ATTR_VALID.

        :raises AssertionError: if the callback has not been called.
        """
        (args, kwargs) = self.get_next_call()
        assert not kwargs
        (call_name, call_value, call_quality) = args
        assert (
            call_name.lower() == self._event_name
        ), f"Event name '{call_name.lower()}'' does not match expected name '{self._event_name}'"
        assert (
            call_value == value
        ), f"Call value {call_value} does not match expected value {value}"
        assert (
            call_quality == quality
        ), f"Call quality {call_quality} does not match expected quality {quality}"

    def assert_not_called(self: MockChangeEventCallback) -> None:  # type: ignore[override]
        """
        Assert if not called.

        :raises AssertionError: change event callback
        """
        call_data = self._fetch_change_event(self._not_called_timeout)
        if call_data is not None:
            (_, call_value, _) = call_data
            raise AssertionError(
                f"Change event callback has been called with {call_value}"
            )

    def assert_last_change_event(
        self: MockChangeEventCallback,
        value: Any,
        _do_assert: bool = True,
        quality: tango.AttrQuality = tango.AttrQuality.ATTR_VALID,
    ) -> None:
        """
        Assert the arguments of the last call to this mock callback.

        The "last" call is the last call before an attempt to get the
        next event times out.

        This is useful for situations where we know a device may fire
        several events, and we don't know or care about the exact order
        of events, but we do know what the final event should be. For
        example, when we tell MccsController to turn on, it has to turn
        many devices on, which have to turn many devices on, etc. With
        so m

        :param value: the asserted value of the change event
        :param quality: the asserted quality of the change event. This
            is optional, with a default of ATTR_VALID.
        :param _do_assert: option to not perform an assert (useful for debugging).

        :raises AssertionError: if the callback has not been called.
        """
        called_mock = None
        failure_message = "Callback has not been called"

        while True:
            timeout = (
                self._called_timeout
                if called_mock is None
                else self._not_called_timeout
            )
            try:
                called_mock = self._queue.get(timeout=timeout)
            except queue.Empty:
                break

            (args, kwargs) = called_mock.call_args
            (call_name, call_value, call_quality) = args

            if call_name.lower() != self._event_name:
                failure_message = (
                    f"Event name '{call_name.lower()}' does not match expected name "
                    f"'{self._event_name}'"
                )
                called_mock = None
                continue

            if call_value != value:
                failure_message = (
                    f"Call value {call_value} does not match expected value {value}"
                )
                called_mock = None
                continue

            if call_quality != quality:
                failure_message = (
                    f"Call quality {call_quality} does not match expected quality "
                    f"{quality}"
                )
                called_mock = None
                continue

        if called_mock is None and _do_assert:
            raise AssertionError(failure_message)

class MockCallableDeque(MockCallable):
    """
    This class alters MockCallable to use a deque instead of a queue and adds the `assert_in_deque` method
    which checks the deque for calls to this mock with specific arguments.

    It is a special case of a :py:class:`MockCallable` where the
    callable will be called in a non-deterministic order.

    This class allows inspection of the deque to find specific calls.
    """

    def __init__(
        self: MockCallableDeque,
        return_value: Any = None,
        called_timeout: float = 5.0,
        not_called_timeout: float = 1.0,
    ):
        """
        Initialise a new instance.

        :param return_value: what to return when called
        :param called_timeout: how long to wait for a call to occur when
            we are expecting one. It makes sense to wait a long time for
            the expected call, as it will generally arrive much much
            sooner anyhow, and failure for the call to arrive in time
            will cause the assertion to fail. The default is 5 seconds.
        :param not_called_timeout: how long to wait for a callback when
            we are *not* expecting one. Since we need to wait the full
            timeout period in order to determine that a callback has not
            arrived, asserting that a call has not been made can
            severely slow down your tests. By keeping this timeout quite
            short, we can speed up our tests, at the risk of prematurely
            passing an assertion. The default is 0.5
        """
        super().__init__(
            return_value=return_value,
            called_timeout=called_timeout,
            not_called_timeout=not_called_timeout,
        )
        self._queue: collections.deque = collections.deque()

    def __call__(self: MockCallableDeque, *args: Any, **kwargs: Any) -> Any:
        """
        Handle a callback call.

        Create a standard mock, call it, and put it on the deque. (This
        approach lets us take advantange of the mock's assertion
        functionality later.)

        :param args: positional args in the call
        :param kwargs: keyword args in the call

        :return: the object's return value
        """
        called_mock = unittest.mock.Mock()
        called_mock(*args, **kwargs)
        self._queue.append(called_mock)
        return self._return_value

    def _fetch_call(self: MockCallableDeque, timeout: float) -> Optional[unittest.mock.Mock]:
        try:
            return self._queue.pop()
        except IndexError:
            return None

    def assert_in_deque(
        self: MockCallableDeque,
        expected_arguments_list: list[Any],
    ) -> bool:
        """
        Assert that a call (or calls) to the callback with the expected arguments are
        present in the deque.

        This method clears matched calls from the deque before returning.

        :param expected_arguments_list: A list of arguments this mock is expected to be called with and found in the deque.

        :returns: `True` if all arguments provided were found in the deque else returns `False`.
        """
        # Extract a list of all the call arguments currently in the deque.
        call_arguments = [queue_item.call_args[0][0] for queue_item in self._queue]
        indices_to_remove = []
        for expected_argument in expected_arguments_list:
            if expected_argument in call_arguments:
                # If we find an expected argument in the list then we remember where in the list it was so we can remove them later.
                # call_arguments will be in the same order as the deque.
                indices_to_remove.append(call_arguments.index(expected_argument))
            else:
                # We couldn't find an expected argument so return False.
                return False

        # Clear found items in ***reverse order***
        indices_to_remove.sort(reverse=True)
        self._remove_elements(indices_to_remove)
        
        # If we get here then we must have found all of our expected_arguments.
        return True

    def assert_ordered_in_deque(
        self: MockCallableDeque,
        expected_arguments_list: list[Any],
    ) -> bool:
        """
        Assert that the mock has been called with the provided arguments in the order specified.

        :param expected_arguments_list: A list of ordered arguments this mock is expected to have been called with.

        :return: `True` if all arguments were found in the deque in the order provided else `False`.
        """
        # Extract a list of all the call arguments currently in the deque.
        call_arguments = [queue_item.call_args[0][0] for queue_item in self._queue]
        indices_to_remove = []
        for actual_argument in call_arguments:
            try:
                # We always want to match against the first in the list.
                if actual_argument == expected_arguments_list[0]:
                    indices_to_remove.append(call_arguments.index(actual_argument))
                    # Remove the found item from our list.
                    expected_arguments_list.pop()
            except IndexError:
                return False

        # If expected_arguments_list is not empty then we didn't find everything or it wasn't in the order we wanted.
        if len(expected_arguments_list) >0:
            return False

        # Clear found items in ***reverse order***
        indices_to_remove.sort(reverse=True)
        self._remove_elements(indices_to_remove)
        # Found all entries in specified order.
        return True

    def _remove_elements(self: MockCallableDeque, indices_to_remove: list[int]) -> None:
        """
        Remove the calls at the index contained in `indices_to_remove`.

        This method is used to clear found calls to the mock.
        :param indices_to_remove: An integer list of indices to be removed from the deque.
        """
        for index in indices_to_remove:
            self._queue.remove(self._queue[index])