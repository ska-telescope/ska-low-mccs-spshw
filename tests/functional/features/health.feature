Feature: Test health
    Test that health is being computed and aggregated correctly

    Scenario: Healthy when everything is on and operational
        Given a DAQ that is online
        And a Subrack that is online
        And a Tile that is online
        And a Station that is online
        And the Station has been commanded to turn to standby
        And the Station reports that its state is STANDBY
        And the Tile reports that its state is OFF
        When the Station has been commanded to turn on
        Then the Station reports that its state is ON
        And the Tile reports that its state is ON
        And the DAQ reports that its HealthState is OK
        And the Subrack reports that its HealthState is OK
        And the Tile reports that its HealthState is OK
        And the Station reports that its HealthState is OK

    Scenario: Failed when tile monitoring point is out of bounds
        Given a Subrack that is online
        And a Tile that is online
        And a Station that is online
        And the Station has been commanded to turn on
        And the Station reports that its state is ON
        And the Tile reports that its state is ON
        And the Subrack reports that its HealthState is OK
        And the Tile reports that its HealthState is OK
        And the Station reports that its HealthState is OK
        When the Tile board temperature thresholds are adjusted
        Then the Tile reports that its HealthState is FAILED
        And the Station reports that its HealthState is FAILED
        And the Subrack reports that its HealthState is OK

    Scenario: Failed when subrack monitoring point is out of bounds
        Given a Subrack that is online
        And a Tile that is online
        And a Station that is online
        And the Station has been commanded to turn on
        And the Station reports that its state is ON
        And the Tile reports that its state is ON
        And the Subrack reports that its HealthState is OK
        And the Tile reports that its HealthState is OK
        And the Station reports that its HealthState is OK
        When the Subrack board temperature thresholds are adjusted
        Then the Tile reports that its HealthState is OK
        And the Station reports that its HealthState is FAILED
        And the Subrack reports that its HealthState is FAILED

    # This isn't really a health scenario but the code exists for these steps already.
    # TODO: Refactor out generic test steps.
    Scenario: Test Standby to On
        Given a Station that is online
        And a Subrack that is online
        And a Tile that is online
        And the Station has been commanded to turn to standby
        And the Station reports that its state is STANDBY
        And the Tile reports that its state is OFF
        When the Tile has been commanded to turn on
        Then the Tile reports that its state is ON
        And the Station reports that its state is ON