Feature: Test station pointing
    Test that a delay can be applied to a beam correctly

    Scenario: Correcting delayed beam
        Given a station that is online
        And a subrack that is online
        And a set of tiles that are in maintenance
        #And a DAQ instance which is online
        And the station is configured
        
        When the station and subcracks are turned on
        And the station is synchronised
        And the test generator is programmed
        #And the scan is run
        #And the beam is corrected with pointing delays

        Then the applitude of the corrected beam is as expected
