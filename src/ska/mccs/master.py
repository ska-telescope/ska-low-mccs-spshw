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
from tango import DebugIt, Except, ErrSeverity
from tango.server import attribute, command
from tango.server import device_property
from tango import DeviceProxy
from tango import DevState

# Additional import
from ska.base import SKAMaster
from ska.base.control_model import AdminMode

from ska.mccs.utils import call_with_json, json_input
import ska.mccs.release as release


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

        self._fqdns = {
            "subarrays": numpy.array(
                [] if self.MccsSubarrays is None else self.MccsSubarrays, dtype=str
            ),
            "stations": numpy.array(
                [] if self.MccsStations is None else self.MccsStations, dtype=str
            ),
        }

        self._subarray_enabled = numpy.zeros(len(self.MccsSubarrays), dtype=numpy.ubyte)

        self._allocated = {}
        for resource in ["stations"]:
            self._allocated[resource] = numpy.zeros(
                len(self._fqdns[resource]), dtype=numpy.ubyte
            )

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
        return tango.DevState.UNKNOWN

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
        assert 1 <= subarray_id <= len(self._fqdns["subarrays"])

        subarray_fqdn = self._fqdns["subarrays"][subarray_id - 1]

        if self._subarray_enabled[subarray_id - 1]:
            Except.throw_exception(
                "API_CommandFailed",
                "Subarray {} is already enabled".format(subarray_fqdn),
                "MccsMaster.EnableSubarray()",
                ErrSeverity.ERR,
            )
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
        assert 1 <= subarray_id <= len(self._fqdns["subarrays"])

        subarray_fqdn = self._fqdns["subarrays"][subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            Except.throw_exception(
                "API_CommandFailed",
                "Subarray {} is already disabled".format(subarray_fqdn),
                "MccsMaster.DisableSubarray()",
                ErrSeverity.ERR,
            )
        else:
            for resource in ["stations"]:
                mask = self._allocated[resource] == subarray_id
                fqdns = list(self._fqdns[resource][mask])
                for fqdn in fqdns:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = 0
            subarray_device = tango.DeviceProxy(subarray_fqdn)
            subarray_device.adminMode = AdminMode.OFFLINE
            self._subarray_enabled[subarray_id - 1] = False

            for resource in self._allocated:
                mask = self._allocated[resource] == subarray_id
                self._allocated[resource][mask] = 0
                allocated = self._allocated[resource]
                allocated[allocated == subarray_id] = 0

    def is_DisableSubarray_allowed(self):

        return self.get_state() not in [
            DevState.FAULT,
            DevState.UNKNOWN,
            DevState.DISABLE,
        ]

    @command(dtype_in="DevString", doc_in="JSON-formatted string")
    @DebugIt()
    @json_input(
        "/home/grm84/software/lfaa-lmc-prototype/schemas/MccsMaster_Allocate_lax.json"
    )
    def Allocate(self, subarray_id, **allocate_stations):
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
        resources = {}
        resources["stations"] = [False] * len(self._fqdns.get("stations"))
        for station_fqdn in allocate_stations.get("stations"):
            proxy = DeviceProxy(station_fqdn)
            id = proxy.stationID
            resources.get("stations")[id - 1] = True

        assert 1 <= subarray_id <= len(self._fqdns["subarrays"])

        subarray_fqdn = self._fqdns["subarrays"][subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            Except.throw_exception(
                "API_CommandFailed",
                "Cannot allocate resources to disabled subarray {}".format(
                    subarray_fqdn
                ),
                "MccsMaster.Allocate()",
                ErrSeverity.ERR,
            )

        for resource in resources:
            if len(resources[resource]) != len(self._allocated[resource]):
                Except.throw_exception(
                    "API_CommandFailed",
                    "Allocation has length {} but there are {} {}.".format(
                        len(resources[resource]),
                        len(self._allocated[resource]),
                        resource,
                    ),
                    "MccsMaster.Allocate()",
                    ErrSeverity.ERR,
                )

            resources[resource] = numpy.array(resources[resource])
            already_allocated = numpy.logical_and.reduce(
                (
                    self._allocated[resource] != 0,
                    self._allocated[resource] != subarray_id,
                    resources[resource],
                )
            )

            if numpy.any(already_allocated):
                already_allocated_fqdns = self._fqdns[resource][
                    numpy.nonzero(already_allocated)
                ]
                Except.throw_exception(
                    "API_CommandFailed",
                    "Cannot allocate {}s already allocated: {}".format(
                        resource, ", ".join(already_allocated_fqdns)
                    ),
                    "MccsMaster.Allocate()",
                    ErrSeverity.ERR,
                )

        to_release = {}
        to_assign = {}
        for resource in resources:
            release_mask = numpy.logical_and(
                self._allocated[resource] == subarray_id,
                numpy.logical_not(resources[resource]),
            )
            to_release[resource] = list(self._fqdns[resource][release_mask])

            assign_mask = numpy.logical_and(
                self._allocated[resource] == 0, resources[resource]
            )
            to_assign[resource] = list(self._fqdns[resource][assign_mask])

        subarray_device = tango.DeviceProxy(subarray_fqdn)

        if any(to_release.values()):
            call_with_json(subarray_device.ReleaseResources, **to_release)
            for resource in ["stations"]:
                for fqdn in to_release[resource]:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = 0

        if any(to_assign):
            call_with_json(subarray_device.AssignResources, **to_assign)
            for resource in ["stations"]:
                for fqdn in to_assign[resource]:
                    device = tango.DeviceProxy(fqdn)
                    device.subarrayId = subarray_id

        for resource in resources:
            self._allocated[resource][self._allocated[resource] == subarray_id] = 0
            self._allocated[resource][resources[resource]] = subarray_id

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
        assert 1 <= subarray_id <= len(self._fqdns["subarrays"])

        subarray_fqdn = self._fqdns["subarrays"][subarray_id - 1]

        if not self._subarray_enabled[subarray_id - 1]:
            Except.throw_exception(
                "API_CommandFailed",
                "Cannot release resources from disabled subarray {}".format(
                    subarray_fqdn
                ),
                "MccsMaster.Release()",
                ErrSeverity.ERR,
            )

        subarray_device = tango.DeviceProxy(subarray_fqdn)
        subarray_device.ReleaseAllResources()
        for resource in ["stations"]:
            mask = self._allocated[resource] == subarray_id
            fqdns = list(self._fqdns[resource][mask])
            for fqdn in fqdns:
                device = tango.DeviceProxy(fqdn)
                device.subarrayId = 0

        for resource in self._allocated:
            allocations = self._allocated[resource]
            allocations[allocations == subarray_id] = 0

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
