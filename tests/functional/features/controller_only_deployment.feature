# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
Feature: Controller Only Deployment
  As a developer,
  I want to turn MCCS ON and OFF,
  So that we can start up and shut down the telescope.

Scenario Outline: Turn ON_OFF MCCS Controller
    Given MccsController is available
    And MccsController is in <initial_state> state
    And MccsController is in <initial_health> healthState
    When MccsController AdminMode is set to <attr_value>
    Then MccsController is in <final_state> state
    And MccsController is in <final_health> healthState

    Examples: on-off
        | initial_state | final_state   | attr_value    | initial_health    | final_health  |
        | 'disable'     | 'on'          | 'ONLINE'      | 'unknown'         | 'ok'          |
# this test will never work as the starting state is disable
#        | 'on'          | 'disable'     | 'OFFLINE'     | 'ok'              | 'unknown'     |
