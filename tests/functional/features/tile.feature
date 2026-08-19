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
        Then the staged calibration coefficients can be read back correctly from the Tile

    Scenario: Apply and read back staged calibration coefficients per channel
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile is available
        When I stage calibration coefficients on the Tile per channel
        Then the staged calibration coefficients can be read back correctly from the Tile

    Scenario: Apply calibration, verify, switch banks, verify, revert
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile is available
        And I stage calibration coefficients on the Tile per antenna
        And the staged calibration coefficients can be read back correctly from the Tile
        When I switch the active calibration bank
        Then the live calibration coefficients can be read back correctly from the Tile

    Scenario: Apply and verify partial calibration updates
        Given an SPS deployment against a real context
        And the SpsStation and tiles are ON
        And the Tile is available
        And I stage calibration coefficients on the Tile for half of the channels
        And I switch the active calibration bank
        And the staged and live calibration coefficients can be read back correctly from the Tile for the first half of channels
        When I stage calibration coefficients on the Tile for the rest of the channels
        And I switch the active calibration bank again
        Then the live calibration coefficients can be read back correctly from the Tile
        And the staged calibration coefficients can be read back correctly from the Tile

    Scenario: Tile monitors a firmware overheating event and can be turned off afterwards
        Given an SPS deployment against HW
        And the SpsStation and tiles are ON
        And the Tile is available
        # Trigger the firmware shutdown. The CPLD will turn off FPGAs for safety
        When the Tile overheats
        # We should be Unprogrammed now. And since the FPGAs are not ON, We can only trust
        # a subset of attribtutes.
        Then the Tile reports the overheat condition as expected
        And the expected CPLD attributes are VALID
        # After this overheating event we can still turn off the TPM.
        When the Tile is powered OFF
        # Check both State and tileprogrammingstate report OFF.
        Then the tile reports it is in the OFF state


# Scenario: Tile state recovered after dev_init
#     Given an SPS deployment against HW
#     And the SpsStation and tiles are ON
#     And the Tile is in an ALARMED state
#     When the Tile TANGO device is restarted
#     Then the Tile comes up in an ALARMED state
