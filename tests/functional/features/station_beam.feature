Feature: Test station pointing
    Test that delays can be applied to a beam correctly

    Scenario: Correcting delayed beam
        Given a station that is online
        And a subrack that is online
        And a set of tiles that are in maintenance
        And a DAQ instance which is online
        And the station is configured
        And the station is synchronised
        And the test generator is programmed to generate a white noise
        And the beamformer is configured
        And the static delays are set to <delay_type>

        When the station and subrack are turned on
        And the beam is corrected for <correction_type>
        And the scan is run

        Then the applitude of the beam is <amplitude>

        Examples:
            | delay type   | correction type | amplitude |
            | 0            | 0               | 100       |
            | 1            | 0               | 1         |
            | 1            | 1               | 100       |