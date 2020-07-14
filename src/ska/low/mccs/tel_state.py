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
# import tango
# from tango import DebugIt
from tango.server import run

# from tango.server import Device
from tango.server import attribute

# from tango.server import command
# from tango.server import device_property
# from tango import AttrQuality
from tango import AttrWriteType

# import enum
from ska.base import SKATelState

# Additional import
# PROTECTED REGION ID(MccsTelState.additionnal_import) ENABLED START #
import ska.low.mccs.release as release

# PROTECTED REGION END #    //  MccsTelState.additionnal_import

__all__ = ["MccsTelState", "main"]


class MccsTelState(SKATelState):
    """
    MccsTelState TANGO device class for the MccsTelState prototype

    **Properties:**

    - Device Property
    """

    # PROTECTED REGION ID(MccsTelState.class_variable) ENABLED START #
    # PROTECTED REGION END #    //  MccsTelState.class_variable

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    elementsStates = attribute(dtype="DevString")

    observationsStates = attribute(dtype="DevString")

    algorithms = attribute(dtype="DevString", access=AttrWriteType.READ_WRITE)

    algorithmsVersion = attribute(dtype="DevString", access=AttrWriteType.READ_WRITE)

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
            device._elements_states = device.elementsStates
            device._observations_states = device.observationsStates
            device._algorithms = device.algorithms
            device._algorithms_version = device.algorithmsVersion
            device._build_state = release.get_release_info()
            device._version_id = release.version

            return (result_code, message)

    def always_executed_hook(self):
        """Method always executed before any TANGO command is executed."""
        # PROTECTED REGION ID(MccsTelState.always_executed_hook) ENABLED START #
        # PROTECTED REGION END #    //  MccsTelState.always_executed_hook

    def delete_device(self):
        """Hook to delete resources allocated in init_device.

        This method allows for any memory or other resources allocated in the
        init_device method to be released.  This method is called by the device
        destructor and by the device Init command.
        """
        # PROTECTED REGION ID(MccsTelState.delete_device) ENABLED START #
        # PROTECTED REGION END #    //  MccsTelState.delete_device

    # ------------------
    # Attributes methods
    # ------------------

    def read_elementsStates(self):
        # PROTECTED REGION ID(MccsTelState.elementsStates_read) ENABLED START #
        """Return the elementsStates attribute."""
        return self._elements_states
        # PROTECTED REGION END #    //  MccsTelState.elementsStates_read

    def read_observationsStates(self):
        # PROTECTED REGION ID(MccsTelState.observationsStates_read) ENABLED START #
        """Return the observationsStates attribute."""
        return self._observations_states
        # PROTECTED REGION END #    //  MccsTelState.observationsStates_read

    def read_algorithms(self):
        # PROTECTED REGION ID(MccsTelState.algorithms_read) ENABLED START #
        """Return the algorithms attribute."""
        return self._algorithms
        # PROTECTED REGION END #    //  MccsTelState.algorithms_read

    def write_algorithms(self, value):
        # PROTECTED REGION ID(MccsTelState.algorithms_write) ENABLED START #
        """Set the algorithms attribute."""
        pass
        # PROTECTED REGION END #    //  MccsTelState.algorithms_write

    def read_algorithmsVersion(self):
        # PROTECTED REGION ID(MccsTelState.algorithmsVersion_read) ENABLED START #
        """Return the algorithmsVersion attribute."""
        return self._algorithms_version
        # PROTECTED REGION END #    //  MccsTelState.algorithmsVersion_read

    def write_algorithmsVersion(self, value):
        # PROTECTED REGION ID(MccsTelState.algorithmsVersion_write) ENABLED START #
        """Set the algorithmsVersion attribute."""
        pass
        # PROTECTED REGION END #    //  MccsTelState.algorithmsVersion_write

    # --------
    # Commands
    # --------


# ----------
# Run server
# ----------


def main(args=None, **kwargs):
    """Main function of the MccsTelState module."""
    # PROTECTED REGION ID(MccsTelState.main) ENABLED START #
    return run((MccsTelState,), args=args, **kwargs)
    # PROTECTED REGION END #    //  MccsTelState.main


if __name__ == "__main__":
    main()
