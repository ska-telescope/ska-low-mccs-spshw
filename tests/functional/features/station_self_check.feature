Feature: Test SpsStation Self Check

    Scenario: Test SpsStation Self Check
        Given an SPS deployment against HW
        And the SpsStation is ON and in ENGINEERING mode
        When I run the SpsStation Self Check
        Then the SpsStation Self Check passes