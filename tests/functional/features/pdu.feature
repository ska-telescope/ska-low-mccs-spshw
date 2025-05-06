Feature: Test pdu
    Test the PDU device

    Scenario: Pdu turns ports ON
        Given an SPS deployment against HW
        And a PDU that is online and ON
        And a subrack that is online and ON
        And all the PDU ports are OFF
        When subrack commands pdu turn ON port
        Then the PDU port turns ON

    Scenario: Pdu turns ports OFF
        Given an SPS deployment against HW
        And a PDU that is online and ON
        And a subrack that is online and ON
        And all the PDU ports are ON
        When subrack commands pdu turn OFF port
        Then the PDU port turns OFF
