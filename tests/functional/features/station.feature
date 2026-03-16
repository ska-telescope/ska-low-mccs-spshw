Feature: Test station
    Test the station device

    @XTP-76882
    Scenario: Synchronising time stamping
        Given an SPS deployment against HW
        And the SpsStation is ON
        When the station is initialised
        Then the station becomes synchronised


    @xfail
    Scenario: TPMs transition directly from OFF to ON to Synchronised
        Given an SPS deployment against HW
        And the SpsStation is STANDBY
        When the SpsStation is turned ON
        Then all TPMs directly transition to Synchronised state


    Scenario: TPMs transition from OFF to ON to Synchronised (workaround allowed)
        Given an SPS deployment against HW
        And the SpsStation is STANDBY
        When the SpsStation is turned ON
        Then all TPMs eventually transition to Synchronised state
