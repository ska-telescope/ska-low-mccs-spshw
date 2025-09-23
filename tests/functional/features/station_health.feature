Feature: Test station health
    Test the station device

    Scenario: Rebooting Tile device causes health state failure
        Given SpsStation is ON
        When Tile 1 is turned OFF
        Then Tile 1 is in programming state Unknown
        Then SPS station is not in a healthy state