Feature: Test the thin slice

    Scenario: Test turning TPM on
        Given the subrack is online
        And the TPM is off
        When the user tells the subrack to turn the TPM on
        Then the subrack reports that the TPM is on
        And the TPM reports that it is on
        And the TPM reports that it is initialised

    Scenario: Test turning TPM off
        Given the TPM is on
        When the user tells the subrack to turn the TPM off
        Then the subrack reports that the TPM is off
        And the TPM reports that it is off

    Scenario: Test data acquisition on TPM
        Given the TPM is on
        And the TPM reports that it is initialised
        When the user tells the TPM to start acquisition
        Then the TPM reports that it is acquiring data
        And the TPM reports that it is synchronised

    Scenario: Test configuring the DAQRX
        Given the DAQRX has not been started
        When the user configures the DAQRX
        Then the DAQRX reports that it has the provided configuration

    Scenario: Test starting the DAQRX
        Given the DAQRX has been configured
        And the DAQRX has not been started 
        When the user starts the DAQRX
        Then the DAQRX reports that it has been started

    Scenario: Test stopping the DAQRX
        Given the DAQRX has been configured
        And the DAQRX has been started 
        When the user stops the DAQRX
        Then the DAQRX reports that it has been stopped

    Scenario: Test sending data from the TPM to the DAQRX
        Given the TPM is on
        And the TPM is acquiring data
        And the DAQRX has been configured
        And the DAQRX has been started
        When the user tells the TPM to send data
        Then the TPM does not report a fault
        And the DAQRX reports that it is successfully receiving data