Feature: PI6 demo equivalent
    Scenario: Test MCCS subarray enabling
        Given we have master and subarray 1
        And master is on
        When we enable subarray 1 on master
        Then subarray 1 should be on
