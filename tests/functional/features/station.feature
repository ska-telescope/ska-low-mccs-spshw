Feature: Test station
    Test the station device

    @XTP-76882
    Scenario: Synchronising time stamping
        Given an SPS deployment against HW
        And the SpsStation is ON
        When the station is initialised
        Then the station becomes synchronised
        And the bandpass daq is receiving bandpasses


    @xfail
    Scenario: TPMs transition directly from OFF to ON to Synchronised
        Given an SPS deployment against HW
        And the SpsStation is STANDBY
        And the SpsStation OnWorkaroundFlag is set to False
        When the SpsStation is turned ON
        Then all TPMs directly transition to Synchronised state


    Scenario: TPMs transition from OFF to ON to Synchronised (workaround allowed)
        Given an SPS deployment against HW
        And the SpsStation is STANDBY
        And the SpsStation OnWorkaroundFlag is set to True
        When the SpsStation is turned ON
        Then all TPMs eventually transition to Synchronised state


    Scenario: Standby commanded during Init takes all TPMs to Off (SKB-1402 regression)
        Given an SPS deployment against HW
        And the station and its tiles are synchronised
        And inheritmode is set to true
        When the SpsStation is instructed to Init, then to Standby as soon as possible
        Then the Standby command completed successfully
        And all TPMs transition to Off state
