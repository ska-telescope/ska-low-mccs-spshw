Feature: tmc <-> mccs interactions

Background:
    Given we have mvplow running an instance of tmc
    And we have mvplow running an instance of mccs

@XTP-1170
Scenario: MCCS Start up low telescope
    Given tmc is ready to issue an on command
    And mccs is ready to receive an on command
    When tmc turns mccs controller on
    Then mccs controller state is on
    And all mccs station states are on

@XTP-1257
Scenario: MCCS Allocate subarray
    Given tmc is ready to allocate a subarray
    And mccs is ready to allocate a subarray
    And subarray obsstate is idle or empty
    When tmc allocates a subarray with valid parameters
    Then the stations have the correct subarray id
    And subarray state is on
    And the subarray obsstate is idle
    And according to allocation policy health of allocated subarray is good
    And other resources are not affected

@XTP-1260
Scenario: MCCS Configure a subarray
    Given we have a successfully allocated subarray
    When tmc configures the subarray
    Then the subarray obsstate is ready
    And subarray health is good

@XTP-1261
Scenario: MCCS Perform a scan on subarray
    Given we have a successfully configured subarray
    When tmc starts a scan on subarray
    Then the subarray obsstate is scanning
