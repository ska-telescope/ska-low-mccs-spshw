Feature: Test station pointing
    Test that delays can be applied to a beam correctly

    Scenario: Correcting delayed beam
        Given a tile_1 that is in mode MAINTENANCE and state ON
        And a tile_2 that is in mode MAINTENANCE and state ON
        And a subrack that is in mode ONLINE and state ON
        And a station that is in mode ONLINE and state ON
        And a DAQ which is in mode ONLINE and state ON
        # And the station is configured
        # And the station and subrack are turned on
        # And the station is synchronised
        # And the test generator is programmed to generate a white noise
        # And the beamformer is configured
        # And the static delays are set to <delay_type>

        # When the beam is corrected for <correction_type>
        # And the scan is run

        # Then the applitude of the beam is approximately <amplitude>

        Examples:
            |   delay type   |   correction type   |   amplitude   |
            | zero delays    | uncorrected         | correct       |
            #| static delays  | uncorrected         | incorrect     |
            #| static delays  | corrected           | correct       |
