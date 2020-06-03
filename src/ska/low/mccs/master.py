# -*- coding: utf-8 -*-
#
# This file is part of the MccsMaster project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MccsMaster Tango device prototype

MccsMaster TANGO device class for the MccsMaster prototype
"""
__all__ = ["MccsMaster", "main"]

import numpy

# PyTango imports
import tango
from tango import DebugIt, DevState
from tango.server import attribute, command, device_property

# Additional import
from ska.base import SKAMaster
from ska.base.control_model import AdminMode

from ska.low.mccs.utils import call_with_json, json_input, tango_raise
import ska.low.mccs.release as release


class MccsMaster(SKAMaster):
    """
    MccsMaster TANGO device class for the MccsMaster prototype

    **Properties:**

    - Device Property
        MccsSubarrays
            - The FQDNs of the Mccs sub-arrays
            - Type: :class:`~tango.DevVarStringArray`
        MccsStations
            - List of MCCS station  TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsStationBeams
            - List of MCCS station beam TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
        MccsTiles
            - List of MCCS Tile TANGO Device names.
            - Type: :class:`~tango.DevVarStringArray`
        MccsAntenna
            - List of MCCS Antenna TANGO Device names
            - Type: :class:`~tango.DevVarStringArray`
    """

    # -----------------
    # Device Properties
    # -----------------

    MccsSubarrays = device_property(dtype="DevVarStringArray")
    MccsStations = device_property(dtype="DevVarStringArray")

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        """Initialises the attributes and properties of the MccsMaster."""
        super().init_device()

        self.set_state(DevState.ON)
        self._build_state = release.get_release_info()
        self._version_id = release.version

        self._subarray_fqdns = numpy.array(
            [] if self.MccsSubarrays is None else self.MccsSubarrays, dtype=str
        )

        # whether subarray is enabled
        self._subarray_enabled = numpy.zeros(len(self.MccsSubarrays), dtype=bool)

        self._station_fqdns = numpy.array(
            [] if self.MccsStations is None else self.MccsStations, dtype=str
        )

        # id of subarray that station is allocated to, zero if unallocated
        self._station_allocated = numpy.zeros(len(self.MccsStations), dtype=numpy.ubyte)

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

    @attribute(
        dtype="DevUShort",
        label="Command progress percentage",
        polling_period=3000,
        rel_change=2,
        abs_change=5,
        max_value=100,
        min_value=0,
        doc="Percentage progress implemented for commands that result in "
        "state/mode transitions for a large \nnumber of components and/or "
        "are executed in stages (e.g power up, power down)",
    )
    def commandProgress(self):

        """Return the commandProgress attribute."""
        return 0

    @attribute(
        dtype="DevUShort",
        unit="s",
        doc="Amount of time it will take to prepare the requested state/mode "
        "transition ? implemented as needed.",
    )
    def commandDelayExpected(self):

        """Return the commandDelayExpected attribute."""
        return 0

    @attribute(dtype="DevState")
    def opState(self):

        """Return the opState attribute."""
        return DevState.UNKNOWN

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def On(self):

        """
        Power off the MCCS system.

        :return: `None`
        """
        pass

    def is_On_allowed(self):

        """ Is the :meth:`On` command alllowed """
        allowed = [DevState.ON, DevState.FAULT, DevState.DISABLE]
        return self.get_state() not in allowed

    @command()
    @DebugIt()
    def Off(self):

        """
        Power off the MCCS system.

        :return: None
        """
        pass

    @command(dtype_out="DevEnum")
    @DebugIt()
    def StandbyLow(self):

        """
        Transition the MCCS system to the low-power STANDBY_LOW_POWER
        operating state.

        :return:  DevEnum
        """
        return 0

    @command(dtype_out="DevEnum")
    @DebugIt()
    def StandbyFull(self):

        """
        standbyFull	None	N/A	DevEnum	OPERATOR	ON, STANDBY_LOW_POWER
        Transition the MCCS system to the STANDBY_FULL_POWER operating state.

        :return:  DevEnum
        """
        return 0

    @command(dtype_out="DevEnum")
    @DebugIt()
    def Operate(self):

        """
        Transit to the OPERATE operating state, ready for signal processing.

        :return:  DevEnum
        """
        return 0

    def is_Operate_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command()
    @DebugIt()
    def Reset(self):

        """
        The MCCS system as a whole is reinitialised as an attempt to clear
        an ALARM or FAULT state.

        :return: None
        """

    @command(dtype_in="DevLong", doc_in="Sub-Array ID")
    @DebugIt()
    def EnableSubarray(self, subarray_id):
        """
        Activate an MCCS Sub-Array

        :param subarray_id: Sub-Array ID
        :type subarray_id: :class:`~tango.DevLong`

        :return: None
        """
        if not (1 <= subarray_id <= len(self._subarray_fqdns)):
            tango_raise("Subarray index {} is out of range".format(subarray_id))

        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]

        if self._subarray_enabled[subarray_id - 1]:
            tango_raise("Subarray {} is already enabled".format(subarray_fqdn))
        else:
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            subarray_device.adminMode = AdminMode.ONLINE
            self._subarray_enabled[subarray_id - 1] = True

    def is_EnableSubarray_allowed(self):
        return self.get_state() not in [
            DevState.FAULT,
            DevState.UNKNOWN,
            DevState.DISABLE,
        ]

    @command(dtype_in="DevLong", doc_in="Sub-Array ID")
    @DebugIt()
    def DisableSubarray(self, subarray_id):

        """
        Deactivate an MCCS Sub-Array

        :param subarray_id: Sub-Array ID
        :type subarray_id: :class:`~tango.DevLong`

        :return: None
        """
        assert 1 <= subarray_id <= len(self._subarray_fqdns)

        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            tango_raise("Subarray {} is already disabled".format(subarray_fqdn))
        else:
            mask = self._station_allocated == subarray_id
            fqdns = self._station_fqdns[mask]
            fqdns = list(fqdns)
            for fqdn in fqdns:
                station = tango.DeviceProxy(fqdn)
                station.subarrayId = 0
            self._station_allocated[mask] = 0

            subarray_device = tango.DeviceProxy(subarray_fqdn)
            subarray_device.adminMode = AdminMode.OFFLINE
            self._subarray_enabled[subarray_id - 1] = False

    def is_DisableSubarray_allowed(self):
        return self.get_state() not in [
            DevState.FAULT,
            DevState.UNKNOWN,
            DevState.DISABLE,
        ]

    @command(dtype_in="DevString", doc_in="JSON-formatted string")
    @DebugIt()
    @json_input("schemas/MccsMaster_Allocate_lax.json")
    def Allocate(self, subarray_id, stations):
        """
        Allocate a set of unallocated MCCS resources to a sub-array.
        The JSON argument specifies the overall sub-array composition in
        terms of which stations should be allocated to the specified Sub-Array.

        :param argin: JSON-formatted string containing an integer
            subarray_id, and arrays of station fqdns.
        :type argin: str

        :return: None

        :example:

        >>> proxy = tango.DeviceProxy("low/elt/master")
        >>> proxy.EnableSubarray(1)
        >>> proxy.Allocate('{"subarray_id":1,
                             "stations": ["mccs/station/01", "mccs/station/02",]}')
        """
        assert 1 <= subarray_id <= len(self._subarray_fqdns)
        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            tango_raise(
                "Cannot allocate resources to disabled subarray {}".format(
                    subarray_fqdn
                )
            )
        station_allocation = numpy.isin(
            self._station_fqdns, stations, assume_unique=True
        )
        already_allocated = numpy.logical_and.reduce(
            (
                self._station_allocated != 0,
                self._station_allocated != subarray_id,
                station_allocation,
            )
        )

        if numpy.any(already_allocated):
            already_allocated_fqdns = list(self._station_fqdns[already_allocated])
            tango_raise(
                "Cannot allocate stations already allocated: {}".format(
                    ", ".join(already_allocated_fqdns)
                ),
            )
        subarray_device = tango.DeviceProxy(subarray_fqdn)

        release_mask = numpy.logical_and(
            self._station_allocated == subarray_id,
            numpy.logical_not(station_allocation),
        )
        if numpy.any(release_mask):
            stations_to_release = list(self._station_fqdns[release_mask])
            call_with_json(
                subarray_device.ReleaseResources, stations=stations_to_release
            )
            for fqdn in stations_to_release:
                device = tango.DeviceProxy(fqdn)
                device.subarrayId = 0

        assign_mask = numpy.logical_and(
            self._station_allocated == 0, station_allocation
        )
        if numpy.any(assign_mask):
            stations_to_assign = list(self._station_fqdns[assign_mask])
            call_with_json(subarray_device.AssignResources, stations=stations_to_assign)
            for fqdn in stations_to_assign:
                device = tango.DeviceProxy(fqdn)
                device.subarrayId = subarray_id

        self._station_allocated[release_mask] = 0
        self._station_allocated[assign_mask] = subarray_id

    def is_Allocate_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command(dtype_in="DevLong", doc_in="Sub-Array ID")
    @DebugIt()
    def Release(self, subarray_id):
        """
        Release a sub-array's Capabilities and resources (stations),
        marking the resources and Capabilities as unassigned and
        idle.

        :param subarray_id: Sub-Array ID
        :type subarray_id: :class:`~tango.DevLong`

        :return: None
        """
        assert 1 <= subarray_id <= len(self._subarray_fqdns)

        subarray_fqdn = self._subarray_fqdns[subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            tango_raise(
                "Cannot release resources from disabled subarray {}".format(
                    subarray_fqdn
                )
            )
        subarray_device = tango.DeviceProxy(subarray_fqdn)
        subarray_device.ReleaseAllResources()
        mask = self._station_allocated == subarray_id
        fqdns = list(self._station_fqdns[mask])
        for fqdn in fqdns:
            device = tango.DeviceProxy(fqdn)
            device.subarrayId = 0
        self._station_allocated[mask] = 0

    def is_Release_allowed(self):

        return self.get_state() not in [
            DevState.OFF,
            DevState.FAULT,
            DevState.INIT,
            DevState.ALARM,
            DevState.UNKNOWN,
            DevState.STANDBY,
            DevState.DISABLE,
        ]

    @command()
    @DebugIt()
    def Maintenance(self):

        """
        Transition the MCCS to a MAINTENANCE state.

        :return: None
        """


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsMaster module."""

    return MccsMaster.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
