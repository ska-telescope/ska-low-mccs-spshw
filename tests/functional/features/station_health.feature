Feature: Test station health
    Test the station device

    Scenario: Station health is failed when Tiles are not synchronized
        Given SpsStation is ON
        When Tile 1 is turned OFF
        Then Tile 1 is in programming state Unknown
        Then SPS station is not in a healthy state