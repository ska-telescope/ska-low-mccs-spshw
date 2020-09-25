Feature: Master-subarray interactions

Background:
    Given we have master
    And we have 2 subarrays
    And we have 2 stations
    And we have 4 tiles

Scenario: Master is turned on
    Given master is off
    And station 1 is off
    And station 2 is off
    And tile 1 is off
    And tile 2 is off
    And tile 3 is off
    And tile 4 is off

    When we turn master on

    Then master should be on
    And station 2 should be on
    And tile 1 should be on
    And tile 2 should be on
    And tile 3 should be on
    And tile 4 should be on

Scenario: Master enables subarray
    Given master is on
    And subarray 1 is off
    And subarray 2 is off

    When we tell master to enable subarray 1
    Then subarray 1 should be on
    And subarray 2 should be off


# Scenario: Master allocates stations to subarrays
#     Given master is on
#     And subarray 1 is on

#     When we tell master to allocate station 1 to subarray 1

#     Then subarray 1's list of allocated stations should be
#         | low/elt/station_1 |
#     And station 1's subarray id should be 1
