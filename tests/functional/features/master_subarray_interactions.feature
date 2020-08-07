Feature: Master-subarray interactions

Scenario: Master enables and disables subarrays
    Given we have master
    And we have 2 subarrays

    When we turn master on
    And we tell master to enable subarray 1
    And we tell master to enable subarray 2
    And we tell master to disable subarray 2

    Then subarray 1 should be on
    And subarray 2 should be off

# Scenario: Master allocates stations to subarrays
#     Given we have master
#     And we have 1 subarrays
#     And we have 1 stations

#     When we turn master on
#     And we tell master to enable subarray 1
#     And we tell master to allocate station 1 to subarray 1

#     Then the stations that subarray 1 thinks are allocated to it should include station 1
#     And the subarray id of station 1 should be subarray 1
