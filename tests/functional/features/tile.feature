Feature: Test tile
    Test the tile device

    @XTP-76880
    Scenario: Flagged packets is ok
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the Tile dropped packets is 0
        When the Tile data acquisition is started
        Then the Tile dropped packets is 0 after 30 seconds
