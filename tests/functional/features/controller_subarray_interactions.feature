Feature: Controller-subarray interactions

Background:
    Given we have controller
    And we have subarray_01
    And we have subarray_02
    And we have station_001
    And we have station_002
    And we have tile_0001
    And we have tile_0002
    And we have tile_0003
    And we have tile_0004

Scenario: Controller is turned on
    Given controller is off
    And station_001 is off
    And station_002 is off
    And tile_0001 is off
    And tile_0002 is off
    And tile_0003 is off
    And tile_0004 is off

    When we turn controller on

    Then controller should be on
    And station_001 should be on
    And station_002 should be on
    And tile_0001 should be on
    And tile_0002 should be on
    And tile_0003 should be on
    And tile_0004 should be on

Scenario: Controller enables subarray
    Given controller is on
    And subarray_01 is off
    And subarray_02 is off

    When we tell controller to enable subarray 1
    Then subarray_01 should be on
    And subarray_02 should be off


# Scenario: Controller allocates stations to subarrays
#     Given controller is on
#     And subarray 1 is on

#     When we tell controller to allocate station 1 to subarray 1

#     Then subarray 1's list of allocated stations should be
#         | low-mccs/station/001 |
#     And station 1's subarray id should be 1
