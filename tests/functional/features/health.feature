Feature: Test health
    Test that health is being computed and aggregated correctly

    Scenario: Healthy when everything is on and operational
        Given the Station is online
        And the Station has been commanded to turn to Standby
        And the Station reports that its state is STANDBY
        And the Tiles reports that its state is OFF
        When the Station has been commanded to turn On
        Then the Station reports that its state is ON
        And the Tiles reports that its state is ON
        And the DAQs reports that its HealthState is OK
        And the Subracks reports that its HealthState is OK
        And the Tiles reports that its HealthState is OK
        And the Station reports that its HealthState is OK

    Scenario: Failed when tile monitoring point is out of bounds
        Given the Station is online
        And the Station has been commanded to turn On
        And the Station reports that its state is ON
        And the Tiles reports that its state is ON
        And the Subracks reports that its HealthState is OK
        And the Tiles reports that its HealthState is OK
        And the Station reports that its HealthState is OK
        When the Tiles board temperature thresholds are adjusted
        Then the Tiles reports that its HealthState is FAILED
        And the Station reports that its HealthState is FAILED
        And the Subracks reports that its HealthState is OK

    Scenario: Failed when subrack monitoring point is out of bounds
        Given the Station is online
        And the Station has been commanded to turn On
        And the Station reports that its state is ON
        And the Tiles reports that its state is ON
        And the Subracks reports that its HealthState is OK
        And the Tiles reports that its HealthState is OK
        And the Station reports that its HealthState is OK
        When the Subracks board temperature thresholds are adjusted
        Then the Tiles reports that its HealthState is OK
        And the Station reports that its HealthState is FAILED
        And the Subracks reports that its HealthState is FAILED

    # This isn't really a health scenario but the code exists for these steps already.
    # TODO: Refactor out generic test steps.
    Scenario: Test Standby to On
        Given the Station is online
        And the Station has been commanded to turn to Standby
        And the Station reports that its state is STANDBY
        And the Tiles reports that its state is OFF
        When the Tiles are commanded to turn On
        Then the Tiles reports that its state is ON
        And the Station reports that its state is ON

    Scenario: Test Station On
        Given the Station is online
        And the Station has been commanded to turn to Standby
        And the Station reports that its state is STANDBY
        And the Tiles reports that its state is OFF
        When the Station has been commanded to turn On
        Then the Tiles reports that its state is ON
        And the Station reports that its state is STANDBY
        And the Station On command finishes
        And the Station reports that its state is ON
        And the Station reports that it is SYNCHRONISED