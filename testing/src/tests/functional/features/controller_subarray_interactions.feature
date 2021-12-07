# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
Feature: tmc <-> mccs interactions

Background:
    Given we have mvplow running an instance of tmc
    And we have mvplow running an instance of mccs

@XTP-1170 @needs_tangodb
Scenario: MCCS Start up low telescope
    Given tmc is ready to issue a startup command
    And mccs is ready to receive a startup command
    When tmc tells mccs controller to start up
    Then mccs controller state is on
    And all mccs station states are on

@XTP-1257 @skip
Scenario: MCCS Allocate subarray
    Given tmc is ready to allocate a subarray
    And mccs is ready to allocate a subarray
    And subarray obsstate is idle or empty
    When tmc allocates a subarray with valid parameters
    Then the stations have the correct subarray id
    And subarray state is on
    And the subarray obsstate is idle
    And according to allocation policy health of allocated subarray is good
    And other resources are not affected

@XTP-1260 @skip
Scenario: MCCS Configure a subarray
    Given we have a successfully allocated subarray
    When tmc configures the subarray
    Then the subarray obsstate is ready
    And subarray health is good

@XTP-1261 @skip
Scenario: MCCS Perform a scan on subarray
    Given we have a successfully configured subarray
    When tmc starts a scan on subarray
    Then the subarray obsstate is scanning

@XTP-1473 @skip
Scenario: MCCS Perform an abort on a scanning subarray
    Given we have a successfully scanning subarray
    When tmc issues an abort on subarray
    Then the subarray obsstate is aborted

@XTP-1762 @skip
Scenario: MCCS Perform an abort on an idle subarray
    Given we have a successfully allocated subarray
    When tmc issues an abort on subarray
    Then the subarray obsstate is aborted

@XTP-1763 @skip
Scenario: MCCS Perform an abort on a configured subarray
    Given we have a successfully configured subarray
    When tmc issues an abort on subarray
    Then the subarray obsstate is aborted
