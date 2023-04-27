Feature: Test station pointing
    Test that a delays can be applied to a beam correctly

    Scenario: Correcting delayed beam
        Given a station that is online, configured and on
        And a subrack that is online and on
        And a set of tiles that are in maintenance and on
        And the station is synchronised
        And the test generator is programmed

        When the beamformer is started
        And the scan is run
        And the pointing delays are corrected

        Then the applitude of the corrected beam is as expected
