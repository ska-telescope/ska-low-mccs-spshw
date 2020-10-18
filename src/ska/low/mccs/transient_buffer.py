# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
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
from ska.base.control_model import HealthState

from ska.low.mccs.events import EventManager
from ska.low.mccs.health import HealthModel

__all__ = ["MccsTransientBuffer", "main"]


class MccsTransientBuffer(MccsDevice):
    """
    MccsTelState TANGO device class for the MccsTransientBuffer prototype.

    This is a subclass of :py:class:`ska.low.mccs.device.MccsDevice`.

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
            """
            Initialises the attributes and properties of the
            `MccsTransientBuffer`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska.base.commands.ResultCode`, str)
            """
            super().do()
            device = self.target
            device._station_id = ""
            device._transient_buffer_job_id = ""
            device._resampling_bits = 0
            device._n_stations = 0
            device._transient_frequency_window = (0.0,)
            device._station_ids = ("",)

            device.event_manager = EventManager(self.logger)
            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                None, None, device.event_manager, device.health_changed
            )

            return (ResultCode.OK, "Init command succeeded")

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~ska.low.mccs.transient_buffer.MccsTransientBuffer.InitCommand.do`
        method of the nested
        :py:class:`~ska.low.mccs.transient_buffer.MccsTransientBuffer.InitCommand`
        class.

        This method allows for any memory or other resources allocated in the
        :py:meth:`~ska.low.mccs.transient_buffer.MccsTransientBuffer.InitCommand.do`
        method to be released. This method is called by the device destructor,
        and by the Init command when the Tango device server is re-initialised.
        """

    # ----------
    # Attributes
    # ----------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state
        changes; responsible for updating the tango side of things i.e.
        making sure the attribute is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska.base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    @attribute(dtype="DevString", label="stationId", polling_period=1000)
    def stationId(self):
        """
        Return the station id

        :return: the station id
        :rtype: int
        """
        return self._station_id

    @attribute(dtype="DevString", label="transientBufferJobId", polling_period=1000)
    def transientBufferJobId(self):
        """
        Return the transient buffer job id

        :return: the transient buffer job id
        :rtype: int
        """
        return self._transient_buffer_job_id

    @attribute(dtype="DevLong", label="resamplingBits", polling_period=1000)
    def resamplingBits(self):
        """
        Return the resampling bit depth

        :return: the resampling bit depth
        :rtype: int
        """
        return self._resampling_bits

    @attribute(dtype="DevShort", label="nStations", polling_period=1000)
    def nStations(self):
        """
        Return the number of stations

        :return: the number of stations
        :rtype: int
        """
        return self._n_stations

    @attribute(
        dtype=("DevDouble",),
        max_dim_x=100,
        label="transientFrequencyWindow",
        polling_period=1000,
    )
    def transientFrequencyWindow(self):
        """
        Return the transient frequency window

        :return: the transient frequency window
        :rtype: sequence of double
        """
        return self._transient_frequency_window

    @attribute(
        dtype=("DevString",), max_dim_x=100, label="stationIds", polling_period=1000
    )
    def stationIds(self):
        """
        Return the station ids

        :return: the station ids
        :rtype: sequence of str
        """
        return self._station_ids


def main(args=None, **kwargs):
    """
    Main function of the :py:mod:`ska.low.mccs.transient_buffer`
    module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return MccsTransientBuffer.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
