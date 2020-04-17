import fire
"""
"Test to make sure fire is installed correctly
def hello(name):
    return 'Can you hear me {name}?' .format(name=name)

if __name__ == '__main__':
    fire.Fire()
"""

import fire
import json
import tango

class MccsTileSimulatorCli():
    def __init__(self):
        #self._dp = tango.DeviceProxy("mccs/tile/01")
        self._dp = tango.DeviceProxy("mccs/tile_simulator/tile1")
        self._dp.command_inout("connect", True)

    def SendBeamData(self, period=0, timeout=0, timestamp=None, seconds=0.2):
        dict = {"Period": period, "Timeout":timeout,
                "Timestamp":timestamp, "Seconds": seconds}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendBeamData", jstr)

    def SendChannelisedDataContinuous(self, channelID=2, nSamples=256, period=10, seconds=0.5):
        dict = {"ChannelID": channelID, "NSamples": nSamples, "Period": period, "Seconds": seconds}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendChannelisedDataContinuous", jstr)

    def SendChannelisedData(self, firstChannel=10, lastChannel=200, seconds=0.5):
        dict = {"FirstChannel": firstChannel, "LastChannel": lastChannel, "Seconds": seconds}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendChannelisedData", jstr)

    def SendRawData(self, sync=True, period=200, seconds=0.5):
        dict = {"Sync":sync, "Period": period, "Seconds": seconds}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendRawData", jstr)

    def ConfigureIntegratedBeamData(self, integration_time=3.142):
        dict = {"IntegrationTime": integration_time}
        jstr = json.dumps(dict)
        self._dp.command_inout("ConfigureIntegratedBeamData", jstr)

    def ConfigureIntegratedChannelData(self, integration_time):
        self._dp.command_inout("ConfigureIntegratedChannelData", 6.284)

    def StartBeamformer(self, startTime=10, duration=20):
        dict = {"StartTime":startTime, "Duration":duration}
        jstr = json.dumps(dict)
        self._dp.command_inout("StartBeamformer", jstr)

    def LoadPointingDelay(self, load_time):
        self._tpm.load_pointing_delay(load_time)

if __name__ == "__main__":
    fire.Fire(MccsTileSimulatorCli)