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

    def SendChannelisedDataContinuous(self, channelID=0, nSamples=128, waitSeconds=0, timeout=0, timestamp=None, seconds=0.2):
#        try:
#            self.SendChannelisedDataContinuous(channelID=None)
#        except tango.DevFailed as df:
#            print("Mandatory Arguement...cannot be a NULL value")
#        else:
            dict = {"ChannelID": channelID, "NSamples": nSamples, "WaitSeconds": waitSeconds, "Timeout": timeout, "Timestamp": timestamp, "Seconds": seconds}
            jstr = json.dumps(dict)
            self._dp.command_inout("SendChannelisedDataContinuous", jstr)

    def SendChannelisedData(self, nSamples=128, firstChannel=0, lastChannel=511, period=0, timeout=0, timestamp=None, seconds=0.2):
        dict = {"NSamples": nSamples, "FirstChannel": firstChannel, "LastChannel": lastChannel, "Period": period, "Timeout": timeout, "Timestamp": timestamp, "Seconds": seconds,}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendChannelisedData", jstr)

    def SendRawData(self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2):
        dict = {"Sync":sync, "Period": period, "Timeout": timeout, "Timestamp": timestamp, "Seconds": seconds}
        jstr = json.dumps(dict)
        self._dp.command_inout("SendRawData", jstr)

    def ConfigureIntegratedBeamData(self, integration_time=0.5):
        self._dp.command_inout("ConfigureIntegratedBeamData", integration_time)

    def ConfigureIntegratedChannelData(self, integration_time=0.5):
        self._dp.command_inout("ConfigureIntegratedChannelData", integration_time)

    def StartBeamformer(self, startTime=0, duration=-1):
        dict = {"StartTime":startTime, "Duration":duration}
        jstr = json.dumps(dict)
        self._dp.command_inout("StartBeamformer", jstr)

    def LoadPointingDelay(self, load_time=0):
        self._dp.command_inout("LoadPointingDelay", load_time)

if __name__ == "__main__":
    fire.Fire(MccsTileSimulatorCli)