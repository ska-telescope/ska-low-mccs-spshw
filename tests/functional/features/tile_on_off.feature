Feature: tile_on_off

    Scenario: Test to turn tile on and off
        Given the subrack is ONLINE
        And the tile is ONLINE
        When the subrack is turned ON
        And the tile is turned ON
        Then the subrack reports the tpm power state is ON
        And the tile reports its state is ON
        When the tile is turned OFF
        Then the subrack reports the tpm power state as OFF
        And the tile reports it's state OFF
