# type: ignore
# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MccsTelState Tango device prototype.

MccsTelState TANGO device class for the MccsTelState prototype
"""

# PyTango imports
from tango.server import run, attribute

# Additional import
from ska_tango_base import SKATelState
from ska_tango_base.control_model import HealthState

import ska_low_mccs.release as release
from ska_low_mccs.health import HealthModel


__all__ = ["MccsTelState", "main"]


class MccsTelState(SKATelState):
    """
    MccsTelState TANGO device class for the MccsTelState prototype.

    This is a subclass of :py:class:`ska_tango_base.SKATelState`.

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------
    def health_changed(self, health):
        """
        Callback to be called whenever the HealthModel's health state changes;
        responsible for updating the tango side of things i.e. making sure the attribute
        is up to date, and events are pushed.

        :param health: the new health value
        :type health: :py:class:`~ska_tango_base.control_model.HealthState`
        """
        if self._health_state == health:
            return
        self._health_state = health
        self.push_change_event("healthState", health)

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKATelState.InitCommand):
        """Command class for device initialisation."""

        def do(self):
            """
            Stateless hook for initialisation of the attributes and properties of the
            :py:class:`.MccsTelState`.

            :return: A tuple containing a return code and a string
                message indicating status. The message is for
                information purpose only.
            :rtype: (:py:class:`~ska_tango_base.commands.ResultCode`, str)
            """
            (result_code, message) = super().do()

            device = self.target
            device._elements_states = ""
            device._observations_states = ""
            device._algorithms = ""
            device._algorithms_version = ""
            device._build_state = release.get_release_info()
            device._version_id = release.version

            device._health_state = HealthState.UNKNOWN
            device.set_change_event("healthState", True, False)
            device.health_model = HealthModel(
                None, None, self.logger, device.health_changed
            )

            return (result_code, message)

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """
        Hook to delete resources allocated in the
        :py:meth:`~.MccsTelState.InitCommand.do` method of the nested
        :py:class:`~.MccsTelState.InitCommand` class.

        This method allows for any memory or other resources allocated
        in the :py:meth:`~.MccsTelState.InitCommand.do` method to be
        released. This method is called by the device destructor, and by
        the Init command when the Tango device server is re-initialised.
        """
        pass

    # ------------------
    # Attributes methods
    # ------------------

    @attribute(dtype="DevString")
    def elementsStates(self):
        """
        Return the elementsStates attribute.

        :todo: What is this?

        :return: the elementsStates attribute
        :rtype: str
        """
        return self._elements_states

    @elementsStates.write
    def elementsStates(self, value):
        """
        Set the elementsStates attribute.

        :todo: What is this?

        :param value: the new elementsStates attribute value
        :type value: str
        """
        self._elements_states = value

    @attribute(dtype="DevString")
    def observationsStates(self):
        """
        Return the observationsStates attribute.

        :todo: What is this?

        :return: the observationsStates attribute
        :rtype: str
        """
        return self._observations_states

    @observationsStates.write
    def observationsStates(self, value):
        """
        Set the observationsStates attribute.

        :todo: What is this?

        :param value: the new observationsStates attribute value
        :type value: str
        """
        self._observations_states = value

    @attribute(dtype="DevString")
    def algorithms(self):
        """
        Return the algorithms attribute.

        :todo: What is this? TBD

        :return: the algorithms attribute
        :rtype: str
        """
        return self._algorithms

    @algorithms.write
    def algorithms(self, value):
        """
        Set the algorithms attribute.

        :todo: What is this? TBD

        :param value: the new value for the algorithms attribute
        :type value: str
        """
        self._algorithms = value

    @attribute(dtype="DevString")
    def algorithmsVersion(self):
        """
        Return the algorithm version.

        :return: the algorithm version
        :rtype: str
        """
        return self._algorithms_version

    @algorithmsVersion.write
    def algorithmsVersion(self, value):
        """
        Set the algorithm version.

        :param value: the new value for the algorithm version
        :type value: str
        """
        self._algorithms_version = value

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """
    Entry point for module.

    :param args: positional arguments
    :type args: list
    :param kwargs: named arguments
    :type kwargs: dict

    :return: exit code
    :rtype: int
    """
    return run((MccsTelState,), args=args, **kwargs)


if __name__ == "__main__":
    main()
