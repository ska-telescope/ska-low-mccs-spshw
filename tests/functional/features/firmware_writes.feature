Feature: Test tile firmware writes
    Test the tile firmware writes and interactions with the database.

    Background:
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And we reached into the database and altered a threshold

    Scenario: Tile firmware thresholds checked after restart
        When the Tile TANGO device is restarted
        Then the Tile reports it has configuration mismatch

    Scenario: Tile firmware thresholds checked after write
        And we have resynced with db
        When we write the thresholds for a different group
        Then the Tile reports it has configuration mismatch

    Scenario: Tile firmware thresholds unset in db
        When we write the thresholds to ignore that group
        Then the Tile reports it has no configuration mismatch

    Scenario: Tile firmware thresholds written to match db
        When we write the thresholds to match
        Then the Tile reports it has no configuration mismatch
