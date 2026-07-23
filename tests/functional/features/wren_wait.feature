Feature: Test WREN wait functionality
    Test the station's WREN wait functionality during initialisation

    Scenario: Station waits for WREN during initialisation when enabled
        Given an SPS deployment against a real context
        And the SpsStation has a WREN TRL
        And the SpsStation WRENHealthCheckEnabled is True
        And the SpsStation is in AdminMode.ONLINE
        And the WREN is initially unhealthy
        When the station is initialised
        And the WREN becomes healthy
        Then the Initialise command completes successfully
        And the station is in DevState.ON

    Scenario: Station times out waiting for WREN when enabled
        Given an SPS deployment against a real context
        And the SpsStation has a WREN TRL
        And the SpsStation WRENHealthCheckEnabled is True
        And the SpsStation WRENHealthCheckTimeout is set to 5 seconds
        And the SpsStation is in AdminMode.ONLINE
        And the WREN is initially unhealthy
        When the station is initialised
        And the WREN remains unhealthy
        Then the Initialise command fails

    Scenario: Station ignores WREN timeout during initialisation when disabled
        Given an SPS deployment against a real context
        And the SpsStation has a WREN TRL
        And the SpsStation WRENHealthCheckEnabled is False
        And the SpsStation WRENHealthCheckTimeout is set to 5 seconds
        And the SpsStation is in AdminMode.ONLINE
        And the WREN is initially unhealthy
        When the station is initialised
        And the WREN remains unhealthy
        Then the Initialise command completes successfully
        And the station is in DevState.ON
