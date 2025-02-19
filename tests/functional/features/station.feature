Feature: Test station
    Test the station device

    @XTP-76882
    Scenario: Synchronising time stamping
        Given an SPS deployment against HW
        And the SpsStation is ON
        And the station is initialised
        When the station is ordered to synchronise
        Then the station becomes synchronised
