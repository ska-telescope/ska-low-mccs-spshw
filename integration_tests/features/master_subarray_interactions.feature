Feature: Master-subarray interactions

Scenario: Test MCCS subarray enabling
    Given we have master
    And we have 1 subarrays

    When we turn master on
    And we tell master to enable subarray 1

    Then subarray 1 should be on
