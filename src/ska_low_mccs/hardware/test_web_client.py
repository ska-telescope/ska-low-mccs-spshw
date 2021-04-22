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
This script contains the tests for the hardware client.
"""
from hardware_client import WebHardwareClient
import time

client = WebHardwareClient("10.0.10.64", 8081)

attributes = [
    "backplane_temperatures",
    "board_temperatures",
    "board_current",
    "subrack_fan_mode",
    "subrack_fan_speeds",
    "subrack_fan_speeds_percent",
    "tpm_voltages",
    "tpm_currents",
    "tpm_powers",
    "tpm_present",
    "tpm_on_off",
    "tpm_supply_fault",
    "power_supply_fan_speeds",
    "power_supply_voltages",
    "power_supply_currents",
    "power_supply_powers",
]

for attr in attributes:
    response = client.get_attribute(attr)
    print(response["status"] + " " + attr + ": " + str(response["value"]))

# Test TPM On Off commands
#
# turn off all tpms
print(str(client.get_attribute("tpm_on_off")["value"]))
response = client.execute_command("turn_off_tpms")
print(response["command"] + ": " + response["status"])
while client.execute_command("command_completed")["retvalue"] is False:
    print("waiting...")
    time.sleep(1)
print(response["command"] + ": completed")
response = client.execute_command("is_tpm_on", 1)
print(
    response["command"] + ": " + response["status"] + " = " + str(response["retvalue"])
)
print(str(client.get_attribute("tpm_on_off")["value"]))

# turn on all tpms
response = client.execute_command("turn_on_tpms")
print(response["command"] + ": " + response["status"])
while client.execute_command("command_completed")["retvalue"] is False:
    print("waiting...")
    time.sleep(1)
print(response["command"] + ": completed")
response = client.execute_command("is_tpm_on", 1)
print(
    response["command"] + ": " + response["status"] + " = " + str(response["retvalue"])
)
print(str(client.get_attribute("tpm_on_off")["value"]))

# turn off tpm 1
response = client.execute_command("turn_off_tpm", 1)
print(response["command"] + ": " + response["status"])
while client.execute_command("command_completed")["retvalue"] is False:
    print("waiting...")
    time.sleep(1)
print(response["command"] + ": completed")
print(str(client.get_attribute("tpm_on_off")["value"]))

# turn on tpm 1
response = client.execute_command("turn_on_tpm", 1)
print(response["command"] + ": " + response["status"])
while client.execute_command("command_completed")["retvalue"] is False:
    print("waiting...")
    time.sleep(1)
print(response["command"] + ": completed")
print(str(client.get_attribute("tpm_on_off")["value"]))

# turn off all tpm
response = client.execute_command("turn_off_tpms")
print(response["command"] + ": " + response["status"])
while client.execute_command("command_completed")["retvalue"] is False:
    print("waiting...")
    time.sleep(1)
print(response["command"] + ": completed")
response = client.execute_command("is_tpm_on", 1)
print(
    response["command"] + ": " + response["status"] + " = " + str(response["retvalue"])
)
print(str(client.get_attribute("tpm_on_off")["value"]))

# Test other commands
#
print("fan mode: " + str(client.get_attribute("subrack_fan_mode")["value"]))
response = client.execute_command("set_fan_mode", "1,0")
print(response["command"] + ": " + response["status"] + " = " + response["retvalue"])

print("fan sped: " + str(client.get_attribute("subrack_fan_speeds_percent")["value"]))
response = client.execute_command("set_subrack_fan_speed", "1,50")
print(response["command"] + ": " + response["status"] + " = " + response["retvalue"])

print("fan speed: " + str(client.get_attribute("subrack_fan_speeds_percent")["value"]))
response = client.execute_command("set_fan_mode", "1,1")
print(response["command"] + ": " + response["status"] + " = " + response["retvalue"])

print("fan mode: " + str(client.get_attribute("subrack_fan_mode")["value"]))
print("fan speed: " + str(client.get_attribute("subrack_fan_speeds")["value"]))
print("PS fan speed: " + str(client.get_attribute("power_supply_fan_speeds")["value"]))
response = client.execute_command("set_power_supply_fan_speed", "1,50")
print(response["command"] + ": " + response["status"] + " = " + response["info"])
print("PS fan speed: " + str(client.get_attribute("power_supply_fan_speeds")["value"]))
