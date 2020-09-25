Feature: Master-subarray interactions

Background:
    Given we have master
    And we have subarray_01
    And we have subarray_02
    And we have station_001
    And we have station_002
    And we have tile_0001
    And we have tile_0002
    And we have tile_0003
    And we have tile_0004

Scenario: Master is turned on
    Given master is off
    And station_001 is off
    And station_002 is off
    And tile_0001 is off
    And tile_0002 is off
    And tile_0003 is off
    And tile_0004 is off

    When we turn master on

    Then master should be on
    And station_001 should be on
    And station_002 should be on
    And tile_0001 should be on
    And tile_0002 should be on
    And tile_0003 should be on
    And tile_0004 should be on

Scenario: Master enables subarray
    Given master is on
    And subarray_01 is off
    And subarray_02 is off

    When we tell master to enable subarray 1
    Then subarray_01 should be on
    And subarray_02 should be off


# Scenario: Master allocates stations to subarrays
#     Given master is on
#     And subarray 1 is on

#     When we tell master to allocate station 1 to subarray 1

#     Then subarray 1's list of allocated stations should be
#         | low/elt/station_1 |
#     And station 1's subarray id should be 1
