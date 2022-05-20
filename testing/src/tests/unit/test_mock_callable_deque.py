#from ska_low_mccs.testing.mock import MockCallable

import unittest
import pytest
from typing import Callable
from ska_low_mccs.testing.mock.mock_callable import MockCallableDeque
from ska_tango_base.control_model import PowerState

@pytest.fixture()
def mock_callback_deque_factory(
    mock_callback_called_timeout: float,
    mock_callback_not_called_timeout: float,
) -> Callable[[], MockCallableDeque]:
    """
    Return a factory that returns a new mock callback using a deque each time it is
    called.

    Use this fixture in tests that need more than one mock_callback. If
    your tests only needs a single mock callback, it is simpler to use
    the :py:func:`mock_callback` fixture.

    :param mock_callback_called_timeout: the time to wait for a mock
        callback to be called when a call is expected
    :param mock_callback_not_called_timeout: the time to wait for a mock
        callback to be called when a call is unexpected

    :return: a factory that returns a new mock callback each time it is
        called.
    """
    return lambda: MockCallableDeque(
        called_timeout=mock_callback_called_timeout,
        not_called_timeout=mock_callback_not_called_timeout,
    )

@pytest.fixture()
def component_state_changed_callback(
    mock_callback_deque_factory: Callable[[], unittest.mock.Mock],
) -> unittest.mock.Mock:
    """
    Return a mock callback for component manager communication status.

    :param mock_callback_factory: fixture that provides a mock callback
        factory (i.e. an object that returns mock callbacks when
        called).

    :return: a mock callback to be called when the communication status
        of a component manager changed.
    """
    return mock_callback_deque_factory()

"""
This function allows testing of the new MockCallableDeque class to ensure that
methods that search for entries in the deque find and return the correct calls.
"""
def test_mock_callable_deque(
    component_state_changed_callback: MockCallableDeque,
):
    # Fill our deque which records calls to component_state_changed_callback
    component_state_changed_callback({'power_state': PowerState.UNKNOWN}, fqdn='low-mccs/tile/0002') # deque index 0
    component_state_changed_callback({'power_state': PowerState.UNKNOWN}, fqdn='low-mccs/tile/0001') # deque index 1
    component_state_changed_callback({'power_state': PowerState.UNKNOWN}, fqdn='low-mccs/apiu/001') # deque index 2
    component_state_changed_callback({'power_state': PowerState.OFF}) # deque index 3
    component_state_changed_callback({'is_configured': False}) # deque index 4
    component_state_changed_callback({'power_state': PowerState.UNKNOWN}, fqdn='low-mccs/antenna/000001') # deque index 5
    component_state_changed_callback({'power_state': PowerState.UNKNOWN, 'is_configured': False}, fqdn='low-mccs/apiu/001') # deque index 6
    component_state_changed_callback({'power_state': PowerState.ON}, fqdn='low-mccs/apiu/001') # deque index 7
    component_state_changed_callback({'power_state': PowerState.OFF}, fqdn='low-mccs/apiu/001') # deque index 8

    # ~~~~~~ test _find_next_call_with_keys ~~~~~~ #
    # here the corresponding deque entries are not consumed by the call
    #print(component_state_changed_callback._find_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback._find_next_call_with_keys('power_state'))
    #print(component_state_changed_callback._find_next_call_with_keys('power_state', 'is_configured', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback._find_next_call_with_keys('power_state', fqdn='low-mccs/apiu/999'))
    #print(component_state_changed_callback._find_next_call_with_keys('is_configured', fqdn='low-mccs/apiu/001'))
    # the resulting output of the above block is
    # >>> (2, {'power_state': <PowerState.UNKNOWN: 0>})
    # >>> (3, {'power_state': <PowerState.OFF: 2>})
    # >>> (6, {'power_state': <PowerState.UNKNOWN: 0>, 'is_configured': False})
    # >>> (None, None)
    # >>> (None, None)
    assert component_state_changed_callback._find_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001') == (2, {'power_state': PowerState.UNKNOWN})
    assert component_state_changed_callback._find_next_call_with_keys('power_state') == (3, {'power_state': PowerState.OFF})
    assert component_state_changed_callback._find_next_call_with_keys('power_state', 'is_configured', fqdn='low-mccs/apiu/001') == (6, {'power_state': PowerState.UNKNOWN, 'is_configured': False})
    assert component_state_changed_callback._find_next_call_with_keys('power_state', fqdn='low-mccs/apiu/999') == (None, None)
    assert component_state_changed_callback._find_next_call_with_keys('is_configured', fqdn='low-mccs/apiu/001') == (None, None)

    # ~~~~~~ test get_next_call_with_keys ~~~~~~ #
    # here the corresponding deque entries are consumed by the call
    #print(component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback.get_next_call_with_keys('power_state'))
    #print(component_state_changed_callback.get_next_call_with_keys('power_state', 'is_configured', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001'))
    #print(component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001'))
    # the resulting output of the above block is
    # >>> (<PowerState.UNKNOWN: 0>,)
    # >>> (<PowerState.OFF: 2>,)
    # >>> (<PowerState.UNKNOWN: 0>, False)
    # >>> (<PowerState.ON: 4>,)
    # >>> (<PowerState.OFF: 2>,)
    # >>> None  # all related calls have been consumed
    assert component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001') == {'power_state': PowerState.UNKNOWN}
    assert component_state_changed_callback.get_next_call_with_keys('power_state') == {'power_state': PowerState.OFF}
    assert component_state_changed_callback.get_next_call_with_keys('power_state', 'is_configured', fqdn='low-mccs/apiu/001') == {'power_state': PowerState.UNKNOWN, 'is_configured': False}
    assert component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001') == {'power_state': PowerState.ON}
    assert component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001') == {'power_state': PowerState.OFF}
    assert component_state_changed_callback.get_next_call_with_keys('power_state', fqdn='low-mccs/apiu/001') == None


    # we consumed some calls during the above block, so our deque now consists of the following calls
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0002')
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0001')
    # call({'is_configured': False})
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/antenna/000001')

    # ~~~~~~ test assert_not_called_with_keys ~~~~~~ #
    # the following assertions will pass
    component_state_changed_callback.assert_not_called_with_keys('health_state')
    component_state_changed_callback.assert_not_called_with_keys('power_state', fqdn='low-mccs/apiu/999')
    # whereas the assertions below should fail
    failed_correctly = False
    try:
        component_state_changed_callback.assert_not_called_with_keys('power_state', fqdn='low-mccs/tile/0002')  
        component_state_changed_callback.assert_not_called_with_keys('is_configured') 
    except:
        failed_correctly = True
    if not failed_correctly:
        raise AssertionError("Method assert_not_called_with_keys failed to raise exception.")


    # add a few more elements to our deque
    component_state_changed_callback({'power_state': PowerState.OFF})
    component_state_changed_callback({'power_state': PowerState.ON})
    component_state_changed_callback({'power_state': PowerState.UNKNOWN})
    component_state_changed_callback({'power_state': PowerState.OFF})
    # our deque now consists of the following calls
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0002')
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0001')
    # call({'is_configured': False})
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/antenna/000001')
    # call({'power_state': <PowerState.OFF: 2>})
    # call({'power_state': <PowerState.ON: 4>})
    # call({'power_state': <PowerState.UNKNOWN: 0>})
    # call({'power_state': <PowerState.OFF: 2>})

    # ~~~~~~ test assert_next_call_with_keys ~~~~~~ #
    # the below assertion would fail
    failed_correctly = False
    try:
        component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.UNKNOWN})
    except:
        failed_correctly = True
    if not failed_correctly:
        raise AssertionError("Method assert_next_call_with_keys failed to raise exception.")
    # whereas these will pass
    component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.OFF})
    component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.ON})
    component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.UNKNOWN})
    component_state_changed_callback.assert_next_call_with_keys({'power_state': PowerState.OFF})

    # we consumed some calls during the above block, so our deque now consists of the following calls
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0002')
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/tile/0001')
    # call({'is_configured': False})
    # call({'power_state': <PowerState.UNKNOWN: 0>}, fqdn='low-mccs/antenna/000001')