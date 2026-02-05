Feature: Test tile
    Test the tile device

    @XTP-76880
    Scenario: Flagged packets is ok
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile dropped packets is 0
        When the Tile data acquisition is started
        Then the Tile dropped packets is 0 after 30 seconds

    Scenario: Tile synchronised state recovered after dev_init
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the Tile is available
        And the Tile is in a defined synchronised state
        When the Tile TANGO device is restarted
        Then the Tile comes up in the defined Synchronised state

    Scenario: Tile initialised state recovered after dev_init
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the Tile is available
        And the Tile is in a defined initialised state
        When the Tile TANGO device is restarted
        Then the Tile comes up in the defined Initialised state

    Scenario: Apply and read back staged calibration coefficients per antenna
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile is available
        When I stage calibration coefficients on the Tile per antenna
        Then the applied calibration coefficients can be read back correctly from the Tile

    Scenario: Apply and read back staged calibration coefficients per channel
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile is available
        When I stage calibration coefficients on the Tile per channel
        Then the applied calibration coefficients can be read back correctly from the Tile

# Scenario: Tile state recovered after dev_init
#     Given an SPS deployment against HW
#     And the SpsStation and tiles are ON
#     And the Tile is in an ALARMED state
#     When the Tile TANGO device is restarted
#     Then the Tile comes up in an ALARMED state
