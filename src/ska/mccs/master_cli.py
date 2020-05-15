# -*- coding: utf-8 -*-
#
# This file is part of the Mccs project.
#
# Used to drive the Command Line Interface for the 
# MCCS Master Device Server.
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

import fire
import json
import tango

"""
The command line interface for the MCCS Master device server. Functionality
to handle passing variables to be added as functionality is added to the
Master DS.
"""
class MccsMasterCli:
    def __init__(self):
        self._dp = tango.DeviceProxy("mccs/master/master1")
        #DeviceProxy to match that declared in Jive declaration

    def On(self):
        self._dp.command_inout("On")

    def Off(self):
        self._dp.command_inout("Off")

    def StandbyLow(self):
        self._dp.command_inout("StandbyLow")

    def StandbyFull(self):
        self._dp.command_inout("StandbyFull")

    def Operate(self):
        self._dp.command_inout("Operate")

    def Reset(self):
        self._dp.command_inout("Reset")

    def EnableSubarray(self, argin):
        """
        subarrayId: int
        """
        dict = {}
        jstr = json.dumps(dict)
        self._dp.command_inout("EnableSubarray", jstr)

    def DisableSubarray(self, argin):
        dict = {}
        jstr = json.dumps(dict)
        self._dp.command_inout("DisableSubarray", jstr)
        """
        subarrayId: int
        """

    def Allocate(self, argin):
        """
        config:string
        """
        dict = {}
        jstr = json.dumps(dict)
        self._dp.command_inout("Allocate", jstr)

    def Release(self, argin):
        dict = {}
        jstr = json.dumps(dict)
        self._dp.command_inout("Release", jstr)
        """
        subarray:int
        """

    def Maintenance(self):
        self._dp.command_inout("Maintenance")

"""
    def read_commandProgress(self):
        self._dp.command_inout("Progress")

    def read_commandDelayExpected(self):
        self._dp.command_inout("Delay Expected")
    
    def read_opState(self):
        self._dp.command_inout("OpState")
"""

if __name__ == "__main__":
    fire.Fire(MccsMasterCli)