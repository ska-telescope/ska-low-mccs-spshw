# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""This module implements the MCCS subarray beam device."""
from __future__ import annotations

import json

from tango.server import attribute, command

from ska_tango_base import SKAObsDevice

from ska_tango_base.commands import ResponseCommand, ResultCode
from ska_tango_base.control_model import HealthState

from ska_low_mccs import release
from ska_low_mccs.component import CommunicationStatus
from ska_low_mccs.subarray_beam import (
    SubarrayBeamComponentManager,
    SubarrayBeamHealthModel,
    SubarrayBeamObsStateModel,
)

__all__ = ["MccsSubarrayBeam", "main"]


class MccsSubarrayBeam(SKAObsDevice):
    """An implementation of a subarray beam Tango device for MCCS."""

    # ---------------
    # Initialisation
    # ---------------
    def _init_state_model(self: MccsSubarrayBeam) -> None:
        super()._init_state_model()
        self._obs_state_model = SubarrayBeamObsStateModel(
            self.logger, self._update_obs_state
        )
        self._health_state = HealthState.UNKNOWN  # InitCommand.do() does this too late.
        self._health_model = SubarrayBeamHealthModel(self.health_changed)
        self.set_change_event("healthState", True, False)

    def create_component_manager(
        self: MccsSubarrayBeam,
    ) -> SubarrayBeamComponentManager:
        """
        Create and return a component manager for this device.

        :return: a component manager for this device.
        """
        return SubarrayBeamComponentManager(
            self.logger,
            self._component_communication_status_changed,
            self._health_model.is_beam_locked_changed,
            self._obs_state_model.is_configured_changed,
        )

    def init_command_objects(self: MccsSubarrayBeam) -> None:
        """Initialises the command handlers for commands supported by this device."""
        super().init_command_objects()

        args = (self.component_manager, self.op_state_model, self.logger)
        self.register_command_object("Configure", self.ConfigureCommand(*args))
        self.register_command_object("Scan", self.ScanCommand(*args))

    class InitCommand(SKAObsDevice.InitCommand):
        """
        A class for :py:class:`~.MccsSubarrayBeam`'s Init command.

        The :py:meth:`~.MccsSubarrayBeam.InitCommand.do` method below is
        called upon :py:class:`~.MccsSubarrayBeam`'s initialisation.
        """

        def do(self: MccsSubarrayBeam.InitCommand) -> tuple[ResultCode, str]:
            """
            Initialises the attributes and properties of the
            :py:class:`.MccsSubarrayBeam`.

            State is managed under the hood; the basic sequence is:

            1. Device state is set to INIT
            2. The do() method is run
            3. Device state is set to the OFF

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            (result_code, message) = super().do()

            device = self.target
            device._build_state = release.get_release_info()
            device._version_id = release.version

            # The health model updates our health, but then the base class super().do()
            # overwrites it with OK, so we need to update this again.
            # TODO: This needs to be fixed in the base classes.
            device._health_state = device._health_model.health_state

            return (result_code, message)

    # ----------
    # Callbacks
    # ----------
    def _component_communication_status_changed(
        self: MccsSubarrayBeam,
        communication_status: CommunicationStatus,
    ) -> None:
        """
        Handle change in communications status between component manager and component.

        This is a callback hook, called by the component manager when
        the communications status changes. It is implemented here to
        drive the op_state.

        :param communication_status: the status of communications
            between the component manager and its component.
        """
        action_map = {
            CommunicationStatus.DISABLED: "component_disconnected",
            CommunicationStatus.NOT_ESTABLISHED: "component_unknown",
            CommunicationStatus.ESTABLISHED: "component_on",  # always-on device
        }

        action = action_map[communication_status]
        if action is not None:
            self.op_state_model.perform_action(action)

        self._health_model.is_communicating(
            communication_status == CommunicationStatus.ESTABLISHED
        )

    def health_changed(self, health):
        """
        Handle change in this device's health state.

        This is a callback hook, called whenever the HealthModel's
        evaluated health state changes. It is responsible for updating
        the tango side of things i.e. making sure the attribute is up to
        date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    # ----------
    # Attributes
    # ----------
    @attribute(dtype="DevLong", format="%i")
    def subarrayId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray id.

        :return: the subarray id
        """
        return self.component_manager.subarray_id

    @attribute(dtype="DevLong", format="%i", max_value=47, min_value=0)
    def subarrayBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the subarray beam id.

        :return: the subarray beam id
        """
        return self.component_manager.subarray_beam_id

    @attribute(dtype=("DevLong",), max_dim_x=512, format="%i")
    def stationIds(self: MccsSubarrayBeam) -> list[int]:
        """
        Return the station ids.

        :return: the station ids
        """
        return self.component_manager.station_ids

    @stationIds.write
    def stationIds(self: MccsSubarrayBeam, station_ids: list[int]) -> None:
        """
        Set the station ids.

        :param station_ids: ids of the stations for this beam
        """
        self.component_manager.station_ids = station_ids

    @attribute(dtype="DevLong", format="%i", max_value=7, min_value=0)
    def logicalBeamId(self: MccsSubarrayBeam) -> int:
        """
        Return the logical beam id.

        :todo: this documentation needs to differentiate logical beam id
            from beam id

        :return: the logical beam id
        """
        return self.component_manager.logical_beam_id

    @logicalBeamId.write
    def logicalBeamId(self: MccsSubarrayBeam, logical_beam_id: int) -> None:
        """
        Set the logical beam id.

        :param logical_beam_id: the logical beam id
        """
        self.component_manager.logical_beam_id = logical_beam_id

    @attribute(
        dtype="DevDouble", unit="Hz", standard_unit="s^-1", max_value=1e37, min_value=0
    )
    def updateRate(self: MccsSubarrayBeam) -> float:
        """
        Return the update rate (in hertz) for this subarray beam.

        :return: the update rate for this subarray beam
        """
        return self.component_manager.update_rate

    @attribute(dtype="DevBoolean")
    def isBeamLocked(self: MccsSubarrayBeam) -> bool:
        """
        Return a flag indicating whether the beam is locked or not.

        :return: whether the beam is locked or not
        """
        return self.component_manager.is_beam_locked

    @isBeamLocked.write
    def isBeamLocked(self: MccsSubarrayBeam, value: bool) -> None:
        """
        Set a flag indicating whether the beam is locked or not.

        :param value: whether the beam is locked or not
        :type value: bool
        """
        self.component_manager.is_beam_locked = value

    @attribute(dtype=(("DevLong",),), max_dim_y=384, max_dim_x=4)
    def channels(self: MccsSubarrayBeam) -> list[list[int]]:
        """
        Return the ids of the channels configured for this beam.

        :return: channel ids
        """
        return self.component_manager.channels

    @attribute(dtype=("DevFloat",), max_dim_x=384)
    def antennaWeights(self: MccsSubarrayBeam) -> list[float]:
        """
        Return the antenna weights configured for this beam.

        :return: antenna weightd
        """
        return self.component_manager.antenna_weights

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def desiredPointing(self: MccsSubarrayBeam) -> list(float):
        """
        Return the desired pointing of this beam.

        :return: the desired point of this beam, conforming to the Sky Coordinate Set definition
        """
        return self.component_manager.desired_pointing

    @desiredPointing.write
    def desiredPointing(self: MccsSubarrayBeam, values: list[float]) -> None:
        """
        Set the desired pointing of this beam.

        * activation time (s) -- value range 0-10^37
        * azimuth position (deg) -- value range 0-360
        * azimuth speed (deg/s) -- value range 0-10^37
        * elevation position (deg) -- value range 0-90
        * elevation rate (deg/s) -- value range 0-10^37

        :param values: the desired pointing of this beam, expressed as a
            sky coordinate set
        """
        self.component_manager.desired_pointing = values

    @attribute(dtype=("DevDouble",), max_dim_x=5)
    def phaseCentre(self: MccsSubarrayBeam) -> list(float):
        """
        Return the phase centre.

        :return: the phase centre
        """
        return self.component_manager.phase_centre

    # --------
    # Commands
    # --------
    class ConfigureCommand(ResponseCommand):
        """Class for handling the Configure(argin) command."""

        SUCCEEDED_MESSAGE = "Configure command completed OK"

        def do(
            self: MccsSubarrayBeam.ConfigureCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Do user-specified Configure functionality.

            This is the do-hook for the
            :py:meth:`.MccsSubarrayBeam.Configure` command

            :param argin: Configuration specification dict as a json
                string
                {
                "subarray_beam_id": 1,
                "station_ids": [1,2],
                "update_rate": 0.0,
                "channels": [[0, 8, 1, 1], [8, 8, 2, 1], [24, 16, 2, 1]],
                "sky_coordinates": [0.0, 180.0, 0.0, 45.0, 0.0],
                "antenna_weights": [1.0, 1.0, 1.0],
                "phase_centre": [0.0, 0.0],
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            config_dict = json.loads(argin)
            result_code = component_manager.configure(
                config_dict.get("subarray_beam_id"),
                config_dict.get("station_ids", []),
                config_dict.get("update_rate"),
                config_dict.get("channels", []),
                config_dict.get("sky_coordinates", []),
                config_dict.get("antenna_weights", []),
                config_dict.get("phase_centre", []),
            )
            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (result_code, "")

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Configure(self: MccsSubarrayBeam, argin: str) -> tuple[ResultCode, str]:
        """
        Configure the subarray_beam with all relevant parameters.

        :param argin: Configuration parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Configure")
        (result_code, status) = handler(argin)
        return [[result_code], [status]]

    class ScanCommand(ResponseCommand):
        """Class for handling the Scan(argin) command."""

        SUCCEEDED_MESSAGE = "Scan command completed OK"

        def do(
            self: MccsSubarrayBeam.ScanCommand, argin: str
        ) -> tuple[ResultCode, str]:
            """
            Stateless do-hook for the
            :py:meth:`.MccsSubarrayBeam.Scan` command

            :param argin: Scan parameters encoded in a json string
                {
                "scan_id": 1,
                "scan_time": 4
                }

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            """
            component_manager = self.target
            kwargs = json.loads(argin)
            result_code = component_manager.scan(
                kwargs.get("scan_id"),
                kwargs.get("scan_time"),
            )
            if result_code == ResultCode.OK:
                return (ResultCode.OK, self.SUCCEEDED_MESSAGE)
            else:
                return (result_code, "")

    @command(dtype_in="DevString", dtype_out="DevVarLongStringArray")
    def Scan(self: MccsSubarrayBeam, argin: str) -> tuple[ResultCode, str]:
        """
        Start a scan on the subarray_beam.

        :param argin: Scan parameters encoded in a json string

        :return: A tuple containing a return code and a string
            message indicating status. The message is for
            information purpose only.
        """
        handler = self.get_command_object("Scan")
        (result_code, status) = handler(argin)
        return [[result_code], [status]]


# ----------
# Run server
# ----------
def main(args: str = None, **kwargs: str) -> int:
    """
    Entry point for module.

    :param args: positional arguments
    :param kwargs: named arguments

    :return: exit code
    """
    return MccsSubarrayBeam.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
