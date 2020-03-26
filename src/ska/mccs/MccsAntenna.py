# -*- coding: utf-8 -*-
#
# This file is part of the MccsAntenna project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

""" LFAA Antenna Device Server

An implementation of the Antenna Device Server for the MCCS based upon
architecture in SKA-TEL-LFAA-06000052-02.
"""
__all__ = ["MccsAntenna", "main"]

# tango imports
from tango import DebugIt
from tango.server import attribute, command

# Additional import
from ska.base import SKABaseDevice


class MccsAntenna(SKABaseDevice):
    """
    An implementation of the Antenna Device Server for the MCCS based upon
    architecture in SKA-TEL-LFAA-06000052-02.
    """

    # -----------------
    # Device Properties
    # -----------------

    # ----------
    # Attributes
    # ----------

    antennaId = attribute(
        dtype="int", label="AntennaID", doc="Global antenna identifier",
    )

    logicalTpmAntenna_id = attribute(
        dtype="int",
        label="logicalTpmAntenna_id",
        doc="Local within Tile identifier for the Antenna TPM\n",
    )

    logicalApiuAntenna_id = attribute(
        dtype="double",
        label="logicalApiuAntenna_id",
        doc="Local within Tile identifier for the Antenna APIU",
    )

    tpmId = attribute(
        dtype="double",
        label="tpmId",
        doc="Global Tile ID to which the atenna is connected",
    )

    apiuId = attribute(dtype="double", label="apiuId",)

    gain = attribute(
        dtype="float", label="gain", doc="The gain set for the antenna",
    )  # force wrap

    rms = attribute(
        dtype="float",
        label="rms",
        doc="The measured RMS of the antenna (monitored)",  # force wrap
    )

    voltage = attribute(dtype="float", label="voltage", unit="volts",)

    temperature = attribute(dtype="float", label="temperature", unit="DegC",)

    xPolarisationFaulty = attribute(dtype="bool", label="xPolarisationFaulty",)

    yPolarisationFaulty = attribute(dtype="bool", label="yPolarisationFaulty",)

    fieldNodeLongitude = attribute(
        dtype="float",
        label="fieldNodeLongitude",
        doc="Longitude of field node (centre) to which antenna is associated.",
    )

    fieldNodeLatitude = attribute(
        dtype="float",
        label="fieldNodeLatitude",
        doc="""Latitude of the field node (centre) to which antenna is
        associated.""",
    )

    altitude = attribute(
        dtype="float",
        label="altitude",
        unit="meters",
        doc="Antenna altitude in meters",
    )

    xDisplacement = attribute(
        dtype="float",
        label="xDisplacement",
        unit="meters",
        doc="Horizontal displacement in meters from field node centre",
    )

    yDisplacement = attribute(
        dtype="float",
        label="yDisplacement",
        unit="meters",
        doc="Vertical displacement in meters from field centre",
    )

    timestampOfLastSpectrum = attribute(
        dtype="str", label="timestampOfLastSpectrum",
    )  # force wrap

    logicalAntennaId = attribute(
        dtype="int",
        label="logicalAntennaId",
        doc="Local (within Tile) antenna identifier",
    )

    xPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="xPolarisationScalingFactor",
    )

    yPolarisationScalingFactor = attribute(
        dtype=("int",), max_dim_x=100, label="yPolarisationScalingFactor",
    )

    calibrationCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="calibrationCoefficient",
        doc="""Calibration coefficient to be applied for the next frequency
        channel in the calibration cycle (archived).
        This is presented as a vector.""",
    )

    pointingCoefficient = attribute(
        dtype=("float",), max_dim_x=100, doc="This is presented as a vector.",
    )

    spectrumX = attribute(dtype=("float",), max_dim_x=100, label="spectrumX",)

    spectrumY = attribute(dtype=("float",), max_dim_x=100, label="spectrumY",)

    position = attribute(dtype=("float",), max_dim_x=100, label="position",)

    delays = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delays",
        doc="Delay for each beam to be applied during the next pointing "
        "update (archived)",
    )

    delayRates = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="delayRates",
        doc="Delay rate for each beam to be applied during the next "
        "pointing update (archived)",
    )

    bandpassCoefficient = attribute(
        dtype=("float",),
        max_dim_x=100,
        label="bandpassCoefficient",
        doc="Bandpass coefficient to apply during next calibration cycle to "
        "flatten the antenna's bandpass (archived)",
    )

    # ---------------
    # General methods
    # ---------------

    def init_device(self):
        SKABaseDevice.init_device(self)

    def always_executed_hook(self):

        pass

    def delete_device(self):

        pass

    # ------------------
    # Attributes methods
    # ------------------

    def read_antennaId(self):

        return 0

    def read_logicalTpmAntenna_id(self):

        return 0

    def read_logicalApiuAntenna_id(self):

        return 0.0

    def read_tpmId(self):

        return 0.0

    def read_apiuId(self):

        return 0.0

    def read_gain(self):

        return 0.0

    def read_rms(self):

        return 0.0

    def read_voltage(self):

        return 0.0

    def read_temperature(self):

        return 0.0

    def read_xPolarisationFaulty(self):

        return False

    def read_yPolarisationFaulty(self):

        return False

    def read_fieldNodeLongitude(self):

        return 0.0

    def read_fieldNodeLatitude(self):

        return 0.0

    def read_altitude(self):

        return 0.0

    def read_xDisplacement(self):

        return 0.0

    def read_yDisplacement(self):

        return 0.0

    def read_timestampOfLastSpectrum(self):

        return ""

    def read_logicalAntennaId(self):

        return 0

    def read_xPolarisationScalingFactor(self):

        return [0]

    def read_yPolarisationScalingFactor(self):

        return [0]

    def read_calibrationCoefficient(self):

        return [0.0]

    def read_pointingCoefficient(self):

        return [0.0]

    def read_spectrumX(self):

        return [0.0]

    def read_spectrumY(self):

        return [0.0]

    def read_position(self):

        return [0.0]

    def read_delays(self):

        return [0.0]

    def read_delayRates(self):

        return [0.0]

    def read_bandpassCoefficient(self):

        return [0.0]

    # --------
    # Commands
    # --------

    @command()
    @DebugIt()
    def PowerOn(self):

        pass

    @command()
    @DebugIt()
    def PowerOff(self):

        pass


# ----------
# Run server
# ----------


def main(args=None, **kwargs):

    return MccsAntenna.run_server(args=args, **kwargs)


if __name__ == "__main__":
    main()
