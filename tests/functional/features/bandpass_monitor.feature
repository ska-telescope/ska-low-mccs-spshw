@XTP-34301
Feature: Test bandpass monitor
    Test that antenna bandpasses can be received and plots of them can be produced

    Background:
        Given we have a target station

    @XTP-34299
    Scenario: Stop bandpass monitor
        Given the DAQ is available
        And no consumers are running
        And the DAQ is configured
        And the bandpass monitor is running
        And the DAQ is started with the integrated channel data consumer
        When the DAQ is commanded to stop monitoring bandpasses
        Then the DAQ reports that it is stopping monitoring bandpasses

    @XTP-34300
    Scenario: Receive bandpass data
        Given the DAQ is available
        And no consumers are running
        And the Tile is available
        And the Subrack is available
        And the DAQ is configured
        And the bandpass monitor is running
        And the DAQ is started with the integrated channel data consumer
        And the Station is synchronised
        And the Station is routed to the DAQ
        When the Station is commanded to send integrated channel data
        Then the DAQ reports that it has received integrated channel data
        And the DAQ saves bandpass data to its relevant attributes

    Scenario: Auto-start bandpass monitoring
        Given a bandpass DAQ device
        When the bandpass DAQ is set ONLINE
        Then the bandpass DAQ is started with the integrated channel data consumer
        And the bandpass DAQ has the bandpass monitor running

