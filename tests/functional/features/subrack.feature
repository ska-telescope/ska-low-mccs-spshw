Feature: Test always-on subrack
    Test that we can monitor and control an always-on subrack.

    Scenario: Monitor and control subrack fan speed
        Given a subrack that is online and on
        And a choice of subrack fan
        And the fan mode is manual
        And the fan's speed setting is 90%
        And the fan's speed is approximately 90% of its maximum

        When I set the fan speed to 100%

        Then the fan's speed setting becomes 100%
        And the fan's speed becomes approximately 100% of its maximum

    Scenario: Turn on a TPM
        Given a subrack that is online and on
        And a choice of TPM
        And the TPM is off

        When I tell the subrack to turn on the TPM

        Then the subrack reports that the TPM is on

    Scenario: Turn off all TPMs
        Given a subrack that is online and on
        And the TPM is on

        When I tell the subrack to turn off all TPMs

        Then the subrack reports that the TPM is off
