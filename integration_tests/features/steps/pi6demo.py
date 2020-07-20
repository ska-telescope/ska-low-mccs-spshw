from behave import given, when, then
from tango import DeviceProxy


@given("we have master and subarray 1")
def step_impl1(context):
    context.master = DeviceProxy("low/elt/master")
    context.subarray = DeviceProxy("low/elt/subarray_1")


@given("master is on")
def step_impl2(context):
    context.master.On()


@when("we enable subarray 1 on master")
def step_impl3(context):
    context.master.EnableSubarray(1)


@then("subarray 1 should be on")
def step_impl4(context):
    context.subarray.adminMode == 0
