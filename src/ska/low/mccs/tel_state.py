# -*- coding: utf-8 -*-
#
# This file is part of the MccsTelState project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" MccsTelState Tango device prototype

MccsTelState TANGO device class for the MccsTelState prototype
"""

# PyTango imports
from tango.server import run, attribute

# Additional import
from ska.base import SKATelState
import ska.low.mccs.release as release


__all__ = ["MccsTelState", "main"]


class MccsTelState(SKATelState):
    """
    MccsTelState TANGO device class for the MccsTelState prototype

    **Properties:**

    - Device Property
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    # ---------------
    # General methods
    # ---------------
    class InitCommand(SKATelState.InitCommand):
        """
        Command class for device initialisation
        """

        def do(self):
            """
            Stateless hook for initialisation of the attributes and
            properties of the MccsTelState.
            """
            (result_code, message) = super().do()

            device = self.target
            device._elements_states = ""
            device._observations_states = ""
            device._algorithms = ""
            device._algorithms_version = ""
            device._build_state = release.get_release_info()
            device._version_id = release.version

            return (result_code, message)

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """

    # ------------------
    # Attributes methods
    # ------------------

    @attribute(dtype="DevString", doc="The elementsStates of the MccsTelState class")
    def elementsStates(self):
        """Return the elementsStates attribute."""
        return self._elements_states

    @elementsStates.write
    def elementsStates(self, value):
        """Set the elementsStates attribute."""
        self._elements_states = value

    @attribute(
        dtype="DevString", doc="The observationsStates of the MccsTelState class"
    )
    def observationsStates(self):
        """Return the observationsStates attribute."""
        return self._observations_states

    @observationsStates.write
    def observationsStates(self, value):
        """Set the observationsStates attribute."""
        self._observations_states = value

    @attribute(dtype="DevString", doc="The algorithms of the MccsTelState class")
    def algorithms(self):
        """Return the algorithms attribute."""
        return self._algorithms

    @algorithms.write
    def algorithms(self, value):
        """Set the algorithms attribute."""
        self._algorithms = value

    @attribute(dtype="DevString", doc="The algorithmsVersion of the MccsTelState class")
    def algorithmsVersion(self):
        """Return the algorithmsVersion attribute."""
        return self._algorithms_version

    @algorithmsVersion.write
    def algorithmsVersion(self, value):
        """Set the algorithmsVersion attribute."""
        self._algorithms_version = value

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsTelState module."""
    return run((MccsTelState,), args=args, **kwargs)


if __name__ == "__main__":
    main()
