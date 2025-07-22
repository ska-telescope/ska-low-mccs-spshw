Feature: Test station
    Test the station device

    @XTP-76882
    Scenario: Synchronising time stamping
        Given an SPS deployment against HW
        And the SpsStation is ON
        When the station is initialised
        Then the station becomes synchronised
