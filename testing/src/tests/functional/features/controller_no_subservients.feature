# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
Feature: client -> mccs interactions

Background:
    Given we have a running instance of mccs

#@XTP-1111 @needs_tangodb
Scenario: MCCS Turn on and off low telescope
    Given mccs is ready to receive commands
    When client tells mccs controller to turn on
    Then mccs controller state is on
    When client tells mccs controller to turn off
    Then mccs controller state is off
