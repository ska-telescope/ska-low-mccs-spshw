Feature: tile_on_off

    Scenario: Test to turn tile on and off
        Given the subrack is ONLINE
        And the tile is ONLINE
        When the subrack is turned ON
        And the tile is turned ON
        Then the subrack reports its state is ON
        And the tile reports its state is ON
        When the tile is turned OFF
        Then the tile reports it's state OFF
        And the subrack reports the tile as OFF
    