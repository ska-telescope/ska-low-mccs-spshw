# -*- coding: utf-8 -*-
#
# This file is part of the MccsTransientBuffer project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Transient Buffer Device Server

An implementation of the Transient Buffer Device Server for the MCCS based upon
architecture in SKA-TEL-LFAA-06000052-02.
"""

# PyTango imports
from tango.server import attribute
from ska.low.mccs import MccsDevice

# Additional import
from ska.base.commands import ResultCode

__all__ = ["MccsTransientBuffer", "main"]


class MccsTransientBuffer(MccsDevice):
    """
    MccsTelState TANGO device class for the MccsTransientBuffer prototype

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ---------------
    # General methods
    # ---------------

    class InitCommand(MccsDevice.InitCommand):
        """
        Command class for device initialisation
        """

        def do(self):
            """Initialises the attributes and properties of the MccsTransientBuffer."""
            super().do()
            device = self.target
            device._station_id = ""
            device._transient_buffer_job_id = ""
            device._resampling_bits = 0
            device._n_stations = 0
            device._transient_frequency_window = (0.0,)
            device._station_ids = ("",)

            device.set_change_event("stationId", True, False)
            device.set_archive_event("stationId", True, False)
            device.set_change_event("transientBufferJobId", True, False)
            device.set_archive_event("transientBufferJobId", True, False)
            device.set_change_event("resamplingBits", True, False)
            device.set_archive_event("resamplingBits", True, False)
            device.set_change_event("nStations", True, False)
            device.set_archive_event("nStations", True, False)
            device.set_change_event("transientFrequencyWindow", True, False)
            device.set_archive_event("transientFrequencyWindow", True, False)
            device.set_change_event("stationIds", True, False)
            device.set_archive_event("stationIds", True, False)

            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ----------
    # Attributes
    # ----------

    @attribute(dtype="DevString", label="stationId")
    def stationId(self):
        """Return the stationId attribute."""
        return self._station_id

    @attribute(dtype="DevString", label="transientBufferJobId")
    def transientBufferJobId(self):
        """Return the transientBufferJobId attribute."""
        return self._transient_buffer_job_id

    @attribute(dtype="DevLong", label="resamplingBits")
    def resamplingBits(self):
        """Return the resamplingBits attribute."""
        return self._resampling_bits

    @attribute(dtype="DevShort", label="nStations")
    def nStations(self):
        """Return the nStations attribute."""
        return self._n_stations

    @attribute(dtype=("DevDouble",), max_dim_x=100, label="transientFrequencyWindow")
    def transientFrequencyWindow(self):
        """Return the transientFrequencyWindow attribute."""
        return self._transient_frequency_window

    @attribute(dtype=("DevString",), max_dim_x=100, label="stationIds")
    def stationIds(self):
        """Return the stationIds attribute."""
        return self._station_ids

    # ------------------
    # Attributes methods
    # ------------------

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsTransientBuffer module."""
    return MccsTransientBuffer.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
