Feature: Test the PDU
    Test that we can monitor a PDU and switch its outlets.

    Scenario: Monitor the PDU
        Given a PDU that is online and on

        Then the PDU reports its model and its number of ports
        And the PDU reports the state of each port

    Scenario: Switch a PDU port on
        Given a PDU that is online and on
        And the PDU is simulated
        And PDU port 3 is off

        When I switch PDU port 3 on

        Then PDU port 3 reports that it is on

    Scenario: Switch a PDU port off
        Given a PDU that is online and on
        And the PDU is simulated
        And PDU port 3 is on

        When I switch PDU port 3 off

        Then PDU port 3 reports that it is off
