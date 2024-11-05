@XTP-21181
Feature: DAQ functionality As a developer, I want to be able to configure the DAQ So that we can send different types of data through

    @XTP-21182
    Scenario Outline: Turning the DAQ on
        Given this test is running against station <expected_station>
        And the DAQ is available
        And the DAQ is in the DISABLE state
        And the DAQ is in health state UNKNOWN
        And the DAQ is in adminMode OFFLINE
        When I set adminMode to ONLINE
        Then the DAQ is in the ON state
        And the DAQ is in health state OK

        Examples:
        |     expected_station    |
        |        ci-1         |
        |     real-daq-1      |
        |  stfc-ral-software  |


    Scenario Outline: Turning the DAQ off
        Given this test is running against station <expected_station>
        And the DAQ is available
        And the DAQ is in the ON state
        And the DAQ is in health state OK
        And the DAQ is in adminMode ONLINE
        When I set adminMode to OFFLINE
        Then the DAQ is in the DISABLE state
        And the DAQ is in health state UNKNOWN

        Examples:
        |      expected_station   |
        |        ci-1         |
        |     real-daq-1      |
        |  stfc-ral-software  |

    @XTP-21184
    Scenario Outline: Configuring the DAQ to raw data
        Given this test is running against station <expected_station>
        And the DAQ is available
        And the DAQ is in the ON state
        And the DAQ is in health state OK
        And the DAQ has no consumers running
        When I send the Start command with raw data
        Then the DAQ is in the ON state
        And the DAQ is in health state OK
        And the DAQ is in raw data mode

        Examples:
        |     expected_station    |
        |        ci-1         |
        |     real-daq-1      |
        |  stfc-ral-software  |

    @XTP-21185
    Scenario Outline: Configuring the DAQ to channelised data
        Given this test is running against station <expected_station>
        And the DAQ is available
        And the DAQ is in the ON state
        And the DAQ is in health state OK
        And the DAQ has no consumers running
        When I send the Start command with channelised data
        Then the DAQ is in the ON state
        And the DAQ is in health state OK
        And the DAQ is in channelised data mode

        Examples:
        |      expected_station   |
        |        ci-1         |
        |     real-daq-1      |
        |  stfc-ral-software  |

# @XTP-21186 @xfail
# Scenario: Applying the calibration values
#     Given the DAQ is available
#     And the DAQ is in the ON state
#     And the DAQ is in health state OK
#     And the DAQ is configured to channelised data
#     When I send the start command
#     Then the DAQ is in the ON state
#     And the DAQ is in health state OK
#     And the DAQ applys the calibration values

# @XTP-21187 @xfail
# Scenario: DAQ error handling
#     Given the DAQ is available
#     And the DAQ is in the ON state
#     And the DAQ is in health state OK
#     And the DAQ is receiving data
#     When the DAQ receives a corrupted stream
#     Then the DAQ should report the error
#     And the DAQ should restart the data acquisition
#     And the DAQ should be in the ON state
#     And the DAQ should be in health state OK