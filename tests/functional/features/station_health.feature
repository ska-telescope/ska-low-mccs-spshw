 Feature: Test Station Health
     Test the station health roll up

     Scenario: Station health is failed when Tiles are not synchronized
         Given the SpsStation is ON
         When Device Tile 1 is restarted
         Then Tile 1 is not in synchronized state
         And an SPS station is in Healthy state
