# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""This module contains the features and scenarios for AcquireDataForCalibration."""

Feature: Acquiring correlator data for calibration.
  As an MCCS developer I want to ensure the SpsStation is capable of acquiring
  the requested number of correlator files for calibration.

  Scenario Outline: Acquiring data for calibration produces the requested correlator files
    Given this test is running against station <expected_station>.
    And the DAQ is available
    And the SpsStation is synchronised
    When I acquire calibration data for channels <first_channel> to <last_channel>
    Then the requested number of correlator files are produced

    Examples: channels to acquire
      | expected_station | first_channel | last_channel |
      | stfc-ral-2       | 64            | 70           |
