from pytest_bdd import scenario, given, when, then, parsers
from tango import DeviceProxy, DevState


@scenario("master_subarray_interactions.feature", "Test MCCS subarray enabling")
def test_subarray_enabling():
    pass


@given("we have master")
def master():
    return DeviceProxy("low/elt/master")


@given(parsers.parse("we have {subarray_count:d} subarrays"))
def subarrays(subarray_count):
    return {
        i: DeviceProxy(f"low/elt/subarray_{i}") for i in range(1, subarray_count + 1)
    }


@when("we turn master on")
def turn_master_on(master):
    master.On()


@when(parsers.parse("we tell master to enable subarray {subarray_id:d}"))
def master_enable_subarray(master, subarray_id):
    master.EnableSubarray(subarray_id)


@then(parsers.parse("subarray {subarray_id:d} should be on"))
def subarray_is_on(subarrays, subarray_id):
    assert subarrays[subarray_id].state() == DevState.ON
