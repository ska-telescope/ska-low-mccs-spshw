"""This module contains the tests of the PaSD bus component manager."""
from __future__ import annotations

from datetime import datetime
from typing import Union

import pytest
from _pytest.fixtures import SubRequest

from ska_low_mccs.pasd_bus import (
    PasdBusSimulator,
    #     PasdBusSimulatorComponentManager,
    #     PasdBusComponentManager,
)


class TestPasdBusSimulator:
    """
    Tests of commands common to the PaSDBus simulator and its component manager.

    Because the PaSD bus component manager passes commands down to the
    PaSD bus simulator, many commands are common. Here we test those
    common commands.
    """

    @pytest.fixture(
        params=[
            "pasd_bus_simulator",
            # "pasd_bus_simulator_component_manager",
            # "pasd_bus_component_manager",
        ]
    )
    def pasd_bus(
        self: TestPasdBusSimulator,
        pasd_bus_simulator: PasdBusSimulator,
        # pasd_bus_simulator_component_manager: PasdBusSimulatorComponentManager,
        # pasd_bus_component_manager: PasdBusComponentManager,
        request: SubRequest,
    ) -> Union[
        PasdBusSimulator,
        # PasdBusSimulatorComponentManager,
        # PasdBusComponentManager
    ]:
        """
        Return the PaSD bus component class object under test.

        This is parametrised to return

        * a PaSD bus simulator,

        * a PaSD bus simulator component manager,

        * a PaSD bus component manager,

        So any test that relies on this fixture will be run thrice.

        :param pasd_bus_simulator: the PaSD bus simulator to return
        :param request: A pytest object giving access to the requesting test
            context.

        :raises ValueError: if parametrized with an unrecognised option

        :return: the PaSD bus component object under test
        """
        # :param pasd_bus_simulator_component_manager: the PaSD bus
        #     simulator component manager to return
        # :param pasd_bus_component_manager: the PaSD bus component
        #     manager to return

        if request.param == "pasd_bus_simulator":
            return pasd_bus_simulator
        # elif request.param == "pasd_bus_simulator_component_manager":
        #     pasd_bus_simulator_component_manager.start_communicating()
        #     return pasd_bus_simulator_component_manager
        # elif request.param == "pasd_bus_component_manager":
        #     pasd_bus_component_manager.start_communicating()
        #     # TODO: Do we need to turn it on here? Or is the PaSD bus an
        #     # always on device?
        #     return pasd_bus_component_manager
        raise ValueError("PaSD bus fixture parametrized with unrecognised option")

    def test_antennas_online(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the antennas online attribute.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.antennas_online == [True] * len(pasd_config["antennas"])

    def test_antennas_forced(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the antennas_forced attribute.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.antennas_forced == [False] * len(pasd_config["antennas"])

    def test_antenna_currents(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the antenna currents.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.antenna_currents == [
            PasdBusSimulator.DEFAULT_ANTENNA_CURRENT
        ] * len(pasd_config["antennas"])

    def test_smartbox_input_voltages(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox input voltages.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_input_voltages == [
            PasdBusSimulator.DEFAULT_SMARTBOX_INPUT_VOLTAGE
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_power_supply_output_voltages(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox power supply output voltages.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_power_supply_output_voltages == [
            PasdBusSimulator.DEFAULT_SMARTBOX_POWER_SUPPLY_OUTPUT_VOLTAGE
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_statuses(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox statuses.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_statuses == [
            PasdBusSimulator.DEFAULT_SMARTBOX_STATUS
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_power_supply_temperatures(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox power supply temperatures.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_power_supply_temperatures == [
            PasdBusSimulator.DEFAULT_SMARTBOX_POWER_SUPPLY_TEMPERATURE
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_outside_temperatures(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox outside temperatures.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_outside_temperatures == [
            PasdBusSimulator.DEFAULT_SMARTBOX_OUTSIDE_TEMPERATURE
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_pcb_temperatures(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox PCB temperatures.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_pcb_temperatures == [
            PasdBusSimulator.DEFAULT_SMARTBOX_PCB_TEMPERATURE
        ] * len(pasd_config["smartboxes"])

    def test_smartbox_fndh_ports(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the smartbox FNDH ports.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.smartbox_fndh_ports == [
            smartbox_config["fndh_port"]
            for smartbox_config in pasd_config["smartboxes"]
        ]

    def test_fndh_psu48v_voltages(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH 48V power supply voltages.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert (
            pasd_bus.fndh_psu48v_voltages
            == PasdBusSimulator.DEFAULT_FNDH_PSU48V_VOLTAGES
        )

    def test_fndh_psu5v_voltage(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH 5V power supply voltage.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert (
            pasd_bus.fndh_psu5v_voltage == PasdBusSimulator.DEFAULT_FNDH_PSU5V_VOLTAGE
        )

    def test_fndh_psu48v_current(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH 48V power supply current.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert (
            pasd_bus.fndh_psu48v_current == PasdBusSimulator.DEFAULT_FNDH_PSU48V_CURRENT
        )

    @pytest.mark.parametrize(
        ("location", "temperature"),
        [
            ("psu48v", PasdBusSimulator.DEFAULT_FNDH_PSU48V_TEMPERATURE),
            ("psu5v", PasdBusSimulator.DEFAULT_FNDH_PSU5V_TEMPERATURE),
            ("pcb", PasdBusSimulator.DEFAULT_FNDH_PCB_TEMPERATURE),
            ("outside", PasdBusSimulator.DEFAULT_FNDH_OUTSIDE_TEMPERATURE),
        ],
    )
    def test_fndh_temperatures(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        location: str,
        temperature: float,
    ) -> None:
        """
        Test a FNDH temperature property.

        :param pasd_bus: the PaSD Bus class object under test.
        :param location: location of the sensor
        :param temperature: expected temperature reading
        """
        assert getattr(pasd_bus, f"fndh_{location}_temperature") == temperature

    def test_fndh_status(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH status.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert pasd_bus.fndh_status == PasdBusSimulator.DEFAULT_FNDH_STATUS

    def test_fndh_service_led_on(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH service led.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert not pasd_bus.fndh_service_led_on
        pasd_bus.fndh_service_led_on = True
        assert pasd_bus.fndh_service_led_on

    def test_fndh_ports_smartbox_connected(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH locally forced power.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        """
        expected_smartbox_connected = [False] * PasdBusSimulator.FNDH_NUMBER_OF_PORTS
        for smartbox_config in pasd_config["smartboxes"]:
            expected_smartbox_connected[smartbox_config["fndh_port"] - 1] = True

        assert pasd_bus.fndh_ports_smartbox_connected == expected_smartbox_connected

    def test_fndh_ports_locally_forced_power(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the FNDH locally forced power.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        assert (
            pasd_bus.fndh_ports_locally_forced_power
            == [False] * PasdBusSimulator.FNDH_NUMBER_OF_PORTS
        )

    @pytest.mark.parametrize("antenna_id", [1])
    def test_antenna_on_off(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        antenna_id: int,
    ) -> None:
        """
        Test turning an antenna on and off.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        :param antenna_id: the antenna number for the antenna to
            turn on and off
        """
        smartbox_id = pasd_config["antennas"][antenna_id - 1]["smartbox_id"]
        fndh_port = pasd_config["smartboxes"][smartbox_id - 1]["fndh_port"]

        expected_antennas_on = [False] * len(pasd_config["antennas"])
        expected_antennas_desired_on = [False] * len(pasd_config["antennas"])
        expected_smartboxes_desired_on = [False] * len(pasd_config["smartboxes"])
        expected_fndh_ports_on = [False] * PasdBusSimulator.FNDH_NUMBER_OF_PORTS

        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on
        assert (
            pasd_bus.smartboxes_desired_power_online == expected_smartboxes_desired_on
        )
        assert (
            pasd_bus.smartboxes_desired_power_offline == expected_smartboxes_desired_on
        )
        assert pasd_bus.fndh_ports_power_present == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_online == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_offline == expected_fndh_ports_on

        pasd_bus.turn_antenna_on(antenna_id)

        expected_antennas_on[antenna_id - 1] = True
        expected_antennas_desired_on[antenna_id - 1] = True
        expected_smartboxes_desired_on[smartbox_id - 1] = True
        expected_fndh_ports_on[fndh_port - 1] = True
        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on
        assert (
            pasd_bus.smartboxes_desired_power_online == expected_smartboxes_desired_on
        )
        assert (
            pasd_bus.smartboxes_desired_power_offline == expected_smartboxes_desired_on
        )
        assert pasd_bus.fndh_ports_power_present == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_online == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_offline == expected_fndh_ports_on

        pasd_bus.turn_antenna_off(antenna_id)
        expected_antennas_on[antenna_id - 1] = False
        expected_antennas_desired_on[antenna_id - 1] = False
        # TODO: smartbox doesn't yet detect that all its antennas are off, and turn
        # itself off; nor does FNDH detect that alls its smartboxes are off, and turn
        # itself off.
        # expected_smartboxes_desired_on[smartbox_id - 1] = False
        # expected_fndh_ports_on[fndh_port - 1] = False

        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on
        assert (
            pasd_bus.smartboxes_desired_power_online == expected_smartboxes_desired_on
        )
        assert (
            pasd_bus.smartboxes_desired_power_offline == expected_smartboxes_desired_on
        )
        assert pasd_bus.fndh_ports_power_present == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_online == expected_fndh_ports_on
        assert pasd_bus.fndh_ports_desired_power_offline == expected_fndh_ports_on

    @pytest.mark.parametrize("antenna_id", [1])
    def test_antenna_breaker_trip(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        antenna_id: int,
    ) -> None:
        """
        Test tripped antenna reporting functionality.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        :param antenna_id: the antenna number for which to simulate
            a breaker trip
        """
        expected_antennas_tripped = [False] * len(pasd_config["antennas"])
        expected_antennas_on = [False] * len(pasd_config["antennas"])
        expected_antennas_desired_on = [False] * len(pasd_config["antennas"])
        assert pasd_bus.antennas_tripped == expected_antennas_tripped
        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on

        pasd_bus.turn_antenna_on(antenna_id)
        expected_antennas_on[antenna_id - 1] = True
        expected_antennas_desired_on[antenna_id - 1] = True
        assert pasd_bus.antennas_tripped == expected_antennas_tripped
        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on

        pasd_bus.simulate_trip(antenna_id)
        expected_antennas_tripped[antenna_id - 1] = True
        expected_antennas_on[antenna_id - 1] = False
        assert pasd_bus.antennas_tripped == expected_antennas_tripped
        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on

        pasd_bus.reset_antenna_breaker(antenna_id)
        expected_antennas_tripped[antenna_id - 1] = False
        expected_antennas_on[antenna_id - 1] = True
        assert pasd_bus.antennas_tripped == expected_antennas_tripped
        assert pasd_bus.antenna_power_states == expected_antennas_on
        assert pasd_bus.antennas_desired_power_online == expected_antennas_desired_on
        assert pasd_bus.antennas_desired_power_offline == expected_antennas_desired_on

    @pytest.mark.parametrize("smartbox_id", [1])
    def test_smartbox_service_leds_on(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        smartbox_id: int,
    ) -> None:
        """
        Test the smartbox service LEDs.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        :param smartbox_id: the smartbox that we'll use to test turning
            the service LED on and off
        """
        expected_leds_on = [False] * len(pasd_config["smartboxes"])
        assert pasd_bus.smartbox_service_leds_on == expected_leds_on

        pasd_bus.set_smartbox_service_led_on(smartbox_id, True)
        expected_leds_on[smartbox_id - 1] = True
        assert pasd_bus.smartbox_service_leds_on == expected_leds_on

        pasd_bus.set_smartbox_service_led_on(smartbox_id, False)
        expected_leds_on[smartbox_id - 1] = False
        assert pasd_bus.smartbox_service_leds_on == expected_leds_on

    @pytest.mark.parametrize("antenna_id", [1])
    def test_get_antenna_info(
        self: TestPasdBusSimulator,
        pasd_config: dict,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        antenna_id: int,
    ) -> None:
        """
        Test the ``get_antenna_info`` method.

        :param pasd_config: the PaSD configuration
        :param pasd_bus: the PaSD Bus class object under test.
        :param antenna_id: the antenna number to use in the test
        """
        antenna_config = pasd_config["antennas"][antenna_id - 1]

        assert pasd_bus.get_antenna_info(antenna_id) == {
            "smartbox_id": antenna_config["smartbox_id"],
            "port_number": antenna_config["smartbox_port"],
            "tpm_number": PasdBusSimulator.DEFAULT_ANTENNA_TPM_NUMBER,
            "tpm_input_number": PasdBusSimulator.DEFAULT_ANTENNA_TPM_INPUT_NUMBER,
        }

    @pytest.mark.parametrize("smartbox_id", [1])
    def test_get_smartbox_info(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        smartbox_id: int,
    ) -> None:
        """
        Test the ``get_smartbox_info`` method.

        :param pasd_bus: the PaSD Bus class object under test.
        :param smartbox_id: the smartbox number to use in the test
        """
        smartbox_info = pasd_bus.get_smartbox_info(smartbox_id)
        assert (
            smartbox_info["modbus_register_map_revision_number"]
            == PasdBusSimulator.MODBUS_REGISTER_MAP_REVISION_NUMBER
        )
        assert (
            smartbox_info["pcb_revision_number"] == PasdBusSimulator.PCB_REVISION_NUMBER
        )
        assert smartbox_info["cpu_id"] == PasdBusSimulator.SMARTBOX_CPU_ID
        assert smartbox_info["chip_id"] == PasdBusSimulator.SMARTBOX_CHIP_ID
        assert (
            smartbox_info["firmware_version"]
            == PasdBusSimulator.DEFAULT_SMARTBOX_FIRMWARE_VERSION
        )
        assert (
            smartbox_info["uptime_integer"] == PasdBusSimulator.DEFAULT_SMARTBOX_UPTIME
        )
        assert smartbox_info["status"] == PasdBusSimulator.DEFAULT_SMARTBOX_STATUS
        assert (
            smartbox_info["led_status_pattern"]
            == PasdBusSimulator.DEFAULT_SMARTBOX_LED_PATTERN
        )
        # Check that the read time is a valid timestamp
        _ = datetime.fromisoformat(smartbox_info["read_time"])

    def test_get_fndh_info(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
    ) -> None:
        """
        Test the ``get_fndh_info`` method.

        :param pasd_bus: the PaSD Bus class object under test.
        """
        fndh_info = pasd_bus.get_fndh_info()
        assert (
            fndh_info["modbus_register_map_revision_number"]
            == PasdBusSimulator.MODBUS_REGISTER_MAP_REVISION_NUMBER
        )
        assert fndh_info["pcb_revision_number"] == PasdBusSimulator.PCB_REVISION_NUMBER
        assert fndh_info["cpu_id"] == PasdBusSimulator.FNDH_CPU_ID
        assert fndh_info["chip_id"] == PasdBusSimulator.FNDH_CHIP_ID
        assert (
            fndh_info["firmware_version"]
            == PasdBusSimulator.DEFAULT_FNDH_FIRMWARE_VERSION
        )
        assert fndh_info["uptime_integer"] == PasdBusSimulator.DEFAULT_FNDH_UPTIME
        assert fndh_info["status"] == PasdBusSimulator.DEFAULT_FNDH_STATUS
        assert (
            fndh_info["led_status_pattern"] == PasdBusSimulator.DEFAULT_FNDH_LED_PATTERN
        )
        # Check that the read time is a valid timestamp
        _ = datetime.fromisoformat(fndh_info["read_time"])

    @pytest.mark.parametrize("smartbox_id", [1])
    def test_update_status(
        self: TestPasdBusSimulator,
        pasd_bus: Union[
            PasdBusSimulator,
            # PasdBusSimulatorComponentManager,
            # PasdBusComponentManager,
        ],
        smartbox_id: int,
    ) -> None:
        """
        Test the ``update_status`` method.

        :param pasd_bus: the PaSD Bus class object under test.
        :param smartbox_id: number of a smartbox to use to check the
            result of updating
        """
        smartbox_info = pasd_bus.get_smartbox_info(smartbox_id)
        fndh_info = pasd_bus.get_fndh_info()

        initial_smartbox_read_time = datetime.fromisoformat(smartbox_info["read_time"])
        initial_fndh_read_time = datetime.fromisoformat(fndh_info["read_time"])
        assert initial_fndh_read_time == initial_smartbox_read_time

        # check that the read time stays the same until we call update_status()
        smartbox_info = pasd_bus.get_smartbox_info(smartbox_id)
        fndh_info = pasd_bus.get_fndh_info()
        new_smartbox_read_time = datetime.fromisoformat(smartbox_info["read_time"])
        new_fndh_read_time = datetime.fromisoformat(fndh_info["read_time"])
        assert new_fndh_read_time == new_smartbox_read_time
        assert new_fndh_read_time == initial_fndh_read_time

        pasd_bus.update_status()

        # check that the read time has advanced now that we've called update_status()
        smartbox_info = pasd_bus.get_smartbox_info(smartbox_id)
        fndh_info = pasd_bus.get_fndh_info()
        new_smartbox_read_time = datetime.fromisoformat(smartbox_info["read_time"])
        new_fndh_read_time = datetime.fromisoformat(fndh_info["read_time"])
        assert new_fndh_read_time == new_smartbox_read_time
        assert new_fndh_read_time > initial_fndh_read_time
