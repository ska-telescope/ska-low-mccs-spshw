
class DevicePool:
    def __init__(self, fqdns):
        self._devices = [DeviceProxy(fqdn) for fqdn in fqdns]

    def On(self):
        async_ids = [device.command_inout_asynch("On") for device in self._devices]

        for (async_id, device) in zip(async_ids, self._devices):
            device.command_inout_reply(async_id, timeout=0)

class DevicePoolSequence:
    def __init__(self, pools):
        self._pools = pools

    def On(self):
        for pool in pools:
            pool.On()




class MccsCabinet(Device):
    def init_device(self):
        super().init_device()
        subrack_pool = DevicePool(self.SubrackFqdns)
        tile_pool = DevicePool(self.TileFqdns)
        self.pool = DevicePoolSequence([subrack_pool, tile_pool])

    @command()
    def On(self):
        self.hardware.on()
        self.pool.On()



