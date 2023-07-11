Feature: Test calibration
    Test that calibration solutions can be stored and loaded correctly

    @XTP-25768
    Scenario: Store a calibration solution
        Given a calibration store that is online
        And the database table is initially empty

        When the calibration store is given a solution to store

        Then the solution is stored in the database

    @XTP-25944
    Scenario: Add a calibration solution to existing table
        Given a calibration store that is online
        And the calibration store database contains calibration solutions

        When the calibration store is given a solution to store

        Then the solution is stored in the database
        And existing data is not overwritten

    @XTP-25989
    Scenario: Load a non-existent calibration solution
        Given a calibration store that is online
        And the calibration store database contains calibration solutions

        When the calibration store tries to get a calibration solution not in the database

        Then the calibration store returns an empty array

    @XTP-25769
    Scenario: Load a calibration solution
        Given a calibration store that is online
        And a field station that is online
        And a station calibrator that is online
        And the calibration store database contains calibration solutions
        And the field station has read the outside temperature

        When the station calibrator tries to get a calibration solution

        Then the correct calibration solution is retrieved

    @XTP-25946
    Scenario: Load a calibration solution with multiple available
        Given a calibration store that is online
        And a field station that is online
        And a station calibrator that is online
        And the calibration store database contains multiple calibration solutions for the same inputs
        And the field station has read the outside temperature

        When the station calibrator tries to get a calibration solution

        Then the most recently stored calibration solution is retrieved