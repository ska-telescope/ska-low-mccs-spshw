Feature: Test tile
    Test the tile device

    Scenario: Flagged packets is ok
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the Tile dropped packets is 0
        When the Tile data acquisition is started
        Then the Tile dropped packets stays 0

    Scenario: Synchronising time stamping
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the tiles are unsynchronised
        When the tiles are ordered to synchronise
        Then the tiles become synchronised
