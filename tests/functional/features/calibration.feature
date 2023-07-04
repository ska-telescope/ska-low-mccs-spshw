Feature: Test calibration
    Test that calibration solutions can be stored and loaded correctly

    Scenario: Store a calibration solution
        Given a calibration store that is online
        And the database table is initially empty

        When the calibration store is given a solution to store

        Then the solution is stored in the database

    Scenario: Load a calibration solution
        Given a calibration store that is online
        And a field station that is online
        And a station calibrator that is online
        And the calibration store database contains calibration solutions
        And the field station has read the outside temperature

        When the station calibrator tries to get a calibration solution

        Then the correct calibration solution is retrieved