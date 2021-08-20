#################
MCCS test harness
#################
MCCS uses pytest for testing, and makes extensive use of pytest
fixtures. For an explanation of fixtures see the `About fixtures`_ in
the pytest documentation.

*********************
Testing Tango devices
*********************
In order to test Tango devices, Tango itself must be running, and the
device(s) under test must be running in one or more Tango device
servers. All this is managed by the ``tango_harness`` fixture.

tango_harness
^^^^^^^^^^^^^
The ``tango_harness`` fixture launches the devices under test in a Tango
context, and provides access to those devices through its
``get_device()`` method.

It depends on other fixtures to provide it with information about what
devices to launch, and their configurations. So we can control the
behaviour of the ``tango_harness`` fixture via our implementation of the
fixtures upon which it depends.

devices_to_load
^^^^^^^^^^^^^^^
The most important of these fixtures is the ``devices_to_load`` fixture.
This returns a dictionary that specifies the devices that are to be
launched, and how they should be configured. The dictionary has the
following keys:

* **path** - When we deploy MCCS for real, the devices are deployed and
  configured based on configuration files. Since device configurations
  can be quite complicated, and we want there to be a single source of
  truth for these configurations, the ``tango_harness`` takes most of
  its information about device configuration straight from these
  configuration files. The ``path`` key should contain the path to the
  configuration file that is to be used for this. Normally this will be
  ``charts/ska-low-mccs/data/configuration.json``. However:

  * if testing a device that never gets deployed (such as a device base
    class) then the device will not be in any of the usual configuration
    files; use ``charts/ska-low-mccs/data/extra.json`` instead.

  * in rare cases, it may be necessary to test against a non-standard
    configuration; in such a case, a new configuration file can be
    created, and the ``path`` made to point to it.

* **package** - this is always ``ska_low_mccs``

* **devices** - this is a list of dictionaries, one for each device
  that is to be launched. Each dictionary specifies a single device that
  is to be launched. A dictionary has the following keys:

  * **name** - the name of the device in the configuration file that is
    to be launched.

  * **proxy** - the name of the client proxy class that is to be used to
    communicate with the device. This will normally be
    ``MccsDeviceProxy``.

  * **patch** - this is an optional key that can be used to provide a
    patched device class to be used in testing. The tests will be run
    against the patched device class, but its configuration will still
    be drawn from the configuration file. This is described in detail in
    the `Patching`_ section below.

Here is an example of a ``devices_to_load`` fixture that specifies a
large number of devices to be launched for an end-to-end integration
test:

.. code-block: python

   @pytest.fixture()
   def devices_to_load():
       return {
           "path": "charts/ska-low-mccs/data/configuration.json",
           "package": "ska_low_mccs",
           "devices": [
               {"name": "controller", "proxy": MccsDeviceProxy},
               {"name": "station_001", "proxy": MccsDeviceProxy},
               {"name": "station_002", "proxy": MccsDeviceProxy},
               {"name": "subrack_01", "proxy": MccsDeviceProxy},
               {"name": "tile_0001", "proxy": MccsDeviceProxy, "patch": PatchedTile},
               {"name": "tile_0002", "proxy": MccsDeviceProxy, "patch": PatchedTile},
               {"name": "tile_0003", "proxy": MccsDeviceProxy, "patch": PatchedTile},
               {"name": "tile_0004", "proxy": MccsDeviceProxy, "patch": PatchedTile},
               {"name": "apiu_001", "proxy": MccsDeviceProxy},
               {"name": "apiu_002", "proxy": MccsDeviceProxy},
               {"name": "antenna_000001", "proxy": MccsDeviceProxy},
               {"name": "antenna_000002", "proxy": MccsDeviceProxy},
               {"name": "antenna_000003", "proxy": MccsDeviceProxy},
               {"name": "antenna_000004", "proxy": MccsDeviceProxy},
               {"name": "antenna_000005", "proxy": MccsDeviceProxy},
               {"name": "antenna_000006", "proxy": MccsDeviceProxy},
               {"name": "antenna_000007", "proxy": MccsDeviceProxy},
               {"name": "antenna_000008", "proxy": MccsDeviceProxy},
           ],
       }

Our tests use the ``tango_harness`` fixture to get proxies to the
devices under test:

.. code-block: python

   def test_controller_health_rollup(self, tango_harness):
       controller = tango_harness.get_device("low-mccs/control/control")
       subrack = tango_harness.get_device("low-mccs/subrack/01")
       ...

The ``tango_harness`` fixture is only able to return proxies to these
devices because it has already launched the devices in a Tango context.
It launched the devices because we provided a ``devices_to_load``
fixture that told it to launch them.

Note that if you do not provide a ``devices_to_load`` fixture, the
``tango_harness`` fixture can will be used, but it will launch a Tango
context with no devices at all in it. This can still be useful in rare
cases. For example, when testing general infrastructure, such as a
device proxy or an even subscription mechanism, we may need the ability
to access Tango devices, yet not need any particular device. In such a
case we can test against a pool of mock devices. See `Mock devices`_
for more information on this.

device_to_load
^^^^^^^^^^^^^^
Most of our tests are unit tests. In unit tests of tango devices, there
is only one device under test, and for this simpler case, we don't need
the full flexibility of the dictionary provided by the
``devices_to_load`` fixture. We can use instead a simpler, flatter
dictonary, provided by ``device_to_load`` fixture.

Here's an example of the ``device_to_load`` fixture for unit testing of
the controller device. In this example, the patched class is provided
via its own fixture.

.. code-block: python

   @pytest.fixture()
   def device_to_load(patched_controller_device_class):
       return {
           "path": "charts/ska-low-mccs/data/configuration.json",
           "package": "ska_low_mccs",
           "device": "controller",
           "proxy": MccsDeviceProxy,
           "patch": patched_controller_device_class,
       }

*****
Mocks
*****
The MCCS test harness uses mocks extensively. For background on mocks
and their use in python, see the `Unittest.mock documentation`_.

Mock devices
^^^^^^^^^^^^
It is common for our devices under test to depend upon other devices
that may not be under test. For example, the MCCS antenna device depends
heavily on both the APIU device for the APIU that supplies power to the
antenna, and the Tile device for the TPM that receives data from the
antenna. Without these devices available, the MCCS antenna device cannot
perform most of its functions. Yet *unit* testing the MCCS antenna
device implies testing it *in isolation*.

We resolve this by creating mock devices for devices that we need but
that are not under test. Two fixtures are available for this:

* **mock_factory** - this fixture returns a new mock device each time it
  is called. In any test scope, you can override this fixture by
  re-implementing it to provide mocks with the special properties that
  you need for the test in that scope. For example, if the device under
  test needs to check the state of various other devices, and our tests
  rely on those various other devices to be in ON state, we can set
  this up by define a ``mock_factory`` fixture that returns mock devices
  that are in state ON:

  .. code-block: python

     @pytest.fixture()
     def mock_factory() -> MockDeviceBuilder:
         builder = MockDeviceBuilder()
         builder.set_state(DevState.ON)
         return builder

  See the :py:class:`ska_low_mccs.testing.mock.mock_device.MockDeviceBuilder`
  API for details on using ``MockDeviceBuilder`` to build mock devices
  easily.

* **initial_mocks** - the ``mock_factory`` fixture is very limited in
  its usefulness, because it only allows a single type of device mock,
  and automatically uses it for all mock devices. It is often necessary
  to have more than one kind of mock in a test. For example, when
  testing MCCS's antenna device, we need a mock APIU device and a mock
  Tile device.  These two mock devices each need to have their own
  distinct behaviours. To achieve this, the ``initial_mocks`` fixture
  provides a dictionary of mock devices, keyed by their FQDN. The
  ``tango_harness`` fixture registers each mock device at the specified
  FQDN, so that any attempt to create a proxy to the device at that FQDN
  gets back a mock as well.

  Below is an example of setting up the initial mocks for testing the
  MCCS antenna device. We create fixtures that specify the FQDN of the
  APIU and tile respectively. We create fixtures that create the mocks
  that we want to use for the APIU and tile respectively. Finally, we
  implement the ``initial_mocks`` fixture, to tell the ``tango_harness``
  fixture which mock to provide when a proxy to a particular FQDN is
  requested:

  .. code-block: python

     @pytest.fixture()
     def apiu_fqdn() -> str:
         return "low-mccs/apiu/001"

     @pytest.fixture()
     def tile_fqdn() -> str:
         return "low-mccs/tile/0001"

     @pytest.fixture()
     def mock_apiu(initial_are_antennas_on: list[bool]) -> unittest.mock.Mock:
         builder = MockDeviceBuilder()
         builder.set_state(tango.DevState.OFF)
         builder.add_command("IsAntennaOn", False)
         builder.add_result_command("On", ResultCode.OK)
         builder.add_result_command("PowerUpAntenna", ResultCode.OK)
         builder.add_result_command("PowerDownAntenna", ResultCode.OK)
         builder.add_attribute("areAntennasOn", initial_are_antennas_on)
         return builder()

     @pytest.fixture()
     def mock_tile() -> unittest.mock.Mock:
         builder = MockDeviceBuilder()
         return builder()

     @pytest.fixture()
     def initial_mocks(
         apiu_fqdn: str,
         mock_apiu: unittest.mock.Mock,
         tile_fqdn: str,
         mock_tile: unittest.mock.Mock,
     ) -> dict[str, unittest.mock.Mock]:
         return {
             apiu_fqdn: mock_apiu,
             tile_fqdn: mock_tile,
         }

Once the ``tango_harness`` has been told to register a mock device at
a given FQDN, any attempt to create a proxy to the device at that FQDN
gets back that mock instead. This applies to both the code under test and
the test itself.

For example, suppose we want to test that when we ask the MCCS antenna
device for the antenna voltage, it returns a value that it has retrieved
from the APIU device via its ``get_antenna_voltage(antenna_id)`` method.
We can do this by:

1. Using ``tango_harness.get_device(fqdn)`` to get the mock APIU device,
   and setting the expected behaviour of that mock, if not already done.

2. Asking the MCCS antenna device for the antenna voltage.

3. Checking that the mock APIU device has been called as expected.

  .. code-block: python

     @pytest.mark.parametrize("voltage", [19.0])
     def test_voltage(
         self,
         tango_harness: TangoHarness,
         device_under_test,
         voltage,
     ):
         mock_apiu = tango_harness.get_device("low-mccs/apiu/001")
         mock_apiu.get_antenna_voltage.return_value = voltage

         # ... some further setup omitted here

         assert device_under_test.voltage == voltage
         assert mock_apiu.get_antenna_voltage.called_once_with(1)


Mock callables
^^^^^^^^^^^^^^
Placeholder for mock callables guidance

********
Patching
********
Placeholder for patching guidance

************************
BDD / acceptance testing
************************
Placeholder for BDD / acceptance testing guidance

*************
Tagging tests
*************
Placeholder for guidance on test tagging


.. _About fixtures: https://docs.pytest.org/en/latest/explanation/fixtures.html
.. _Unittest.mock documentation: https://docs.python.org/3/library/unittest.mock.html