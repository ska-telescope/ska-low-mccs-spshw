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
        And the delays are set to <delay_type>

        When the station and subcrack are turned on
        And the scan is run
        And the beam is corrected with <correction_type>

        Then the applitude of the corrected beam is as expected

        Examples:
            | delay type   | correction type |
            | zero delay   | no correction   |
            | static delay | no correction   |
            | static delay | beam corrected  |