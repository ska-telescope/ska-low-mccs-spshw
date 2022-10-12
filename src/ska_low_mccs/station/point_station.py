# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
# Distributed under the terms of the BSD 3-clause new license.
# See LICENSE for more info.
"""
MCCS pointing calculation prototype.

This is originally from the AAVS code.
"""

from __future__ import annotations  # allow forward references in type hints

import logging
import multiprocessing
import queue
import time
import warnings
from datetime import datetime
from typing import Any, Callable, Optional

import fire
import numpy as np
from astropy.constants import c
from astropy.coordinates import AltAz, Angle, EarthLocation, SkyCoord, get_sun
from astropy.time import TimeDelta
from astropy.time.core import Time
from astropy.utils.exceptions import AstropyWarning

warnings.simplefilter("ignore", category=AstropyWarning)

__author__ = "Alessio Magro"

antennas_per_tile = 16


class AntennaInformation(object):
    """Class for holding a station's antenna information."""

    def __init__(self: AntennaInformation) -> None:
        """
        Initialize AntennaInformation object.

        By default it will have 256 elements but no displacements, &c.
        """
        self.nof_elements = 256
        self.xyz: Optional[np.ndarray] = None
        self.elementid: Optional[np.ndarray] = None
        self.tpmid: Optional[np.ndarray] = None

    def load_displacements(self: AntennaInformation, txtfile: str) -> None:
        """
        Load antenna displacements from a text file.

        The file is formatted as per AAVS_loc_italia_190429.txt
        This 4 float-formatted columns separated by spaces.
        The column order is - Element x y TPM
        The header line is skipped.
        x and y units are metres

        :param txtfile: displacements file
        """
        aavs2 = np.loadtxt(txtfile, skiprows=1)
        self.nof_elements = aavs2.shape[0]
        self.xyz = np.append(aavs2[:, 1:3], np.zeros((self.nof_elements, 1)), axis=1)
        self.elementid = aavs2[:, 0].astype(int)
        self.tpmid = aavs2[:, 3].astype(int)


class StationInformation(object):
    """Class for holding information about a station."""

    def __init__(self: StationInformation) -> None:
        """
        Initialize a new instance.

        The instance is initialise with no location data and with a
        default AntennaInformation object (which will have no element
        displacement data).
        """
        self.latitude: Optional[float] = None
        self.longitude: Optional[float] = None
        self.ellipsoidalheight: Optional[float] = None
        self.antennas = AntennaInformation()

    def load_displacements(self: StationInformation, antennafile: str) -> None:
        """
        Proxy to the method in the associated AntennaInformation object.

        :param antennafile: displacements file
        """
        self.antennas.load_displacements(antennafile)

    def set_location(
        self: StationInformation,
        latitude: float,
        longitude: float,
        ellipsoidalheight: float,
    ) -> None:
        """
        Set the location data for this station.

        :param latitude: the latitude of the station (WGS84)
        :param longitude: the longitude of the station (WGS84)
        :param ellipsoidalheight: the ellipsoidal height of the station
        """
        assert latitude <= 90.0 and latitude >= -90.0
        self.latitude = latitude
        assert longitude <= 180.0 and longitude >= -180.0
        self.longitude = longitude
        # Probably this range could be narrowed
        assert ellipsoidalheight >= -107.0 and ellipsoidalheight <= 8870.5
        self.ellipsoidalheight = ellipsoidalheight


class Pointing(object):
    """Helper class for generating beamforming coefficients."""

    def __init__(self: Pointing, station_info: StationInformation) -> None:
        """
        Pointing class, generates delay and delay rates to be downloaded to TPMs.

        :param station_info: Basic information for station location and antenna
            displacements
        """
        # Store arguments
        self.station = station_info

        # Get station location
        self._longitude = self.station.longitude
        self._latitude = self.station.latitude
        self._height = self.station.ellipsoidalheight

        # Initial az/el pointing
        self._az = 0.0
        self._el = 0.0

        self._antennas = self.station.antennas
        self._nof_antennas = self._antennas.nof_elements

        # Get reference antenna location
        self._reference_antenna_loc = EarthLocation.from_geodetic(
            self._longitude,
            self._latitude,
            height=self._height,
            ellipsoid="WGS84",
        )

        # Placeholder for delays and flag for below horizon
        self._below_horizon = False
        self._delays: np.ndarray = None  # type: ignore[assignment]
        self._delay_rates: np.ndarray = None  # type: ignore[assignment]

    # -------------------------------- POINTING FUNCTIONS --------------------------
    def point_to_sun(self: Pointing, pointing_time: Optional[float] = None) -> None:
        """
        Generate delays to point towards the sun for the given time.

        :param pointing_time: Time at which delays should be generated
        """
        # If no time is specified, get current time
        if pointing_time is None:
            pointing_time = Time(datetime.utcnow(), scale="utc")

        # Get sun position in RA, DEC and convert to Alz, Az in telescope
        # reference frame
        sun_position = get_sun(pointing_time)
        alt, az = self._ra_dec_to_alt_az(
            sun_position.ra,
            sun_position.dec,
            pointing_time,
            self._reference_antenna_loc,
        )

        # Compute delays
        self.point_array_static(alt, az)

    def point_array_static(
        self: Pointing,
        altitude: float,
        azimuth: float,
        pointing_time: Optional[float] = None,
    ) -> None:
        """
        Calculate the delay given the altitude and azimuth coordinates of a sky object.

        :param altitude: altitude coordinates of a sky object as astropy angle
        :param azimuth: azimuth coordinates of a sky object as astropy angles
        :param pointing_time: the time at which the pointing will be active
        """
        _ = pointing_time

        # Type conversions if required
        altitude_angle = self.convert_to_astropy_angle(altitude)
        azimuth_angle = self.convert_to_astropy_angle(azimuth)

        self._az = azimuth_angle.value
        self._el = altitude_angle.value

        # Set above horizon flag
        if altitude_angle < 0.0:
            self._below_horizon = True
        else:
            self._below_horizon = False

        # Compute the delays
        self._delays = self._delays_from_altitude_azimuth(  # type: ignore[assignment]
            altitude_angle.rad, azimuth_angle.rad
        )
        self._delay_rates = self._delays * 0

    def point_array(
        self: Pointing,
        right_ascension: float,
        declination: float,
        pointing_time: Optional[float] = None,
        delta_time: float = 1.0,
    ) -> None:
        """
        Calculate the phase shift between two antennas.

        Which is given by the phase constant (2 * pi / wavelength)
        multiplied by the projection of the baseline vector onto the
        plane wave arrival vector

        :param right_ascension: Right ascension of source - stropy Angle / string
            convertable to Angle
        :param declination: Declination of source - astropy Angle / string
            convertable to Angle
        :param pointing_time: Time of observation (in format astropy time)
        :param delta_time: Delta timing for calculating delay rate

        :return: The (delay,delay rate) tuple for each antenna
        """
        # If no time is specified, get current time
        if pointing_time is None:
            pointing_time = Time(datetime.utcnow(), scale="utc")

        # Type conversions if required
        right_ascension = self.convert_to_astropy_angle(right_ascension)
        declination = self.convert_to_astropy_angle(declination)

        # Calculate required delay
        alt, az = self._ra_dec_to_alt_az(
            right_ascension,
            declination,
            Time(pointing_time),
            self._reference_antenna_loc,
        )

        # If required source is not above horizon, generate zeros
        if alt < 0.0:
            self._delays = np.zeros(self._nof_antennas)
            self._delay_rates = np.zeros(self._nof_antennas)
            self._below_horizon = True
            return

        # Generate delays from calculated altitude and azimuth
        self.point_array_static(altitude=alt, azimuth=az)

        # Calculate required delay rate
        if delta_time == 0.0:
            self._delay_rates = self._delays * 0
        else:
            pointing_time = pointing_time + TimeDelta(delta_time, format="sec")
            alt, az = self._ra_dec_to_alt_az(
                right_ascension,
                declination,
                Time(pointing_time),
                self._reference_antenna_loc,
            )
            # TODO: This code needs investigation
            self._delay_rates = (
                self._delays_from_altitude_azimuth(alt.rad, az.rad) - self._delays
            )

        # Set above horizon flag
        self._below_horizon = False

    def get_pointing_coefficients(
        self: Pointing, start_channel: int, nof_channels: int
    ) -> Optional[tuple[np.complex]]:  # type: ignore[name-defined]
        """
        Get complex pointing coefficients from generated delays.

        :param start_channel: Start channel index
        :param nof_channels: Number of channels starting with start_channel

        :returns: Return the pointing coefficients as a tuple of numpy complex values
        """
        if self._delays is None:
            logging.error("No pointing delays generated")
            return None

        # If below horizon flat is set, return 0s
        if self._below_horizon:
            return np.zeros(
                (self._nof_antennas, nof_channels), dtype=np.complex
            )  # type: ignore[return-value, attr-defined]

        # Compute frequency range
        channel_bandwidth = 400e6 / 512.0
        frequencies = np.array(
            [
                start_channel * channel_bandwidth + i * channel_bandwidth
                for i in range(nof_channels)
            ]
        )

        # Generate coefficients
        coefficients = np.zeros(
            (self._nof_antennas, nof_channels), dtype=np.complex
        )  # type: ignore[attr-defined]
        for i in range(nof_channels):
            delays = 2.0 * np.pi * frequencies[i] * self._delays
            coefficients[:, i] = np.cos(delays) + 1j * np.sin(delays)

        # All done, return coefficients
        return coefficients  # type: ignore[return-value]

    def _delays_from_altitude_azimuth(
        self: Pointing, altitude: float, azimuth: float
    ) -> list[float]:
        """
        Calculate the delay using a target altitude Azimuth.

        :param altitude: The altitude of the target astropy angle
        :param azimuth: The azimuth of the target astropy angle

        :return: The delay in seconds for each antenna
        """
        # Calculate transformation
        scale = np.array(
            [
                np.cos(altitude) * np.sin(azimuth),
                np.cos(altitude) * np.cos(azimuth),
                np.sin(altitude),
            ]
        )

        # Apply to antenna displacements
        assert self._antennas.xyz is not None  # for the type checker
        path_length = np.dot(scale, self._antennas.xyz.T)

        # Return frequency-independent geometric delays
        return np.multiply(1.0 / c.value, path_length)

    @staticmethod
    def _ra_dec_to_alt_az(
        right_ascension: float,
        declination: float,
        time: float,
        location: float,
    ) -> list[Angle]:
        """
        Calculate the altitude and azimuth coordinates of a sky object.

        From right ascension and declination and time.

        :param right_ascension: Right ascension of source -
            astropy Angle / string convertable to Angle
        :param declination: Declination of source - astropy Angle / string
            convertable to Angle
        :param time: Time of observation (as astropy Time")
        :param location: astropy EarthLocation

        :return: List containing altitude and azimuth of source as astropy angle
        """
        # Initialise SkyCoord object using the default frame (ICRS) and convert to
        # horizontal coordinates (altitude/azimuth) from the antenna's perspective.
        sky_coordinates = SkyCoord(ra=right_ascension, dec=declination, unit="deg")
        altaz = sky_coordinates.transform_to(AltAz(obstime=time, location=location))

        return [altaz.alt, altaz.az]

    @staticmethod
    def convert_to_astropy_angle(angle: str | float | Angle) -> Angle:
        """
        Convert a number or string to an Astropy angle.

        :param angle: angle

        :return: converted angle
        """
        if type(angle) is not Angle:
            return Angle(angle)
        return angle

    def is_above_horizon(
        self: Pointing,
        right_ascension: float,
        declination: float,
        pointing_time: float,
    ) -> bool:
        """
        Check if the target is above the horizon, given time for the reference antenna.

        :param right_ascension: The right ascension of the target as a astropy angle
        :param declination: The declination of the target as an astropy angle.
        :param pointing_time: The observation time as an astropy Time.

        :return: True if the target coordinates are above the horizon at the specified
            time, false otherwise.
        """
        alt, _ = self._ra_dec_to_alt_az(
            Angle(right_ascension),
            Angle(declination),
            Time(pointing_time),
            self._reference_antenna_loc,
        )

        return alt > 0.0


class PointingDriver:  # pragma: no cover
    """
    The class provides the Fire CLI interface to the Pointing class.

    The methods of the class provide the commands for the CLI.
    """

    def __init__(self: PointingDriver) -> None:
        """
        Initialize point_driver object with a default StationInformation.

        Setup for array centre and create the Pointing object.

        Otherwise leave everything at None.
        """
        self.dispfile = None
        self.calc: Optional[Callable] = None
        self.point_kwargs: dict[str, Any] = {}
        station = StationInformation()
        station.set_location(-26.82472208, 116.7644482, 346.36)
        self.pointing = Pointing(station)
        self._results: list[dict[str, Any]] = []

    def statpos(
        self: PointingDriver, lat: float, lon: float, height: float
    ) -> PointingDriver:
        """
        Command to set the station reference position.

        :param lat: latitude (WGS84, decimal degrees north)
        :param lon: longitude (WGS84, decimal degrees east)
        :param height: Ellipsoidal height (m)

        :return: self - ready for another command
        """
        self.pointing.station.set_location(lat, lon, height)
        return self

    def displacements(self: PointingDriver, file: str) -> PointingDriver:
        """
        Load the station antenna displacements from file.

        :param file: displacements file

        :return: self - ready for another command
        """
        self.pointing.station.load_displacements(file)
        assert self.pointing.station.antennas.xyz is not None  # for the type checker
        print(f"xyz array shape: {self.pointing.station.antennas.xyz.shape}")
        return self

    def azel(self: PointingDriver, az: str, el: str) -> PointingDriver:
        """
        Generate static delays to point to the given azimuth and elevation.

        :param az: Azimuth in format parseable by astropy e.g. 180d
        :param el: Elevation in format parseable by astropy e.g. 45d

        :return: self - ready for another command
        """
        self.calc = self.pointing.point_array_static
        self.point_kwargs["altitude"] = el
        self.point_kwargs["azimuth"] = az

        print(f"Point station to az={az}, el={el}")
        return self

    def radec(self: PointingDriver, ra: str, dec: str) -> PointingDriver:
        """
        Generate delays and rates to track the given Right Ascension and Declination.

        :param ra: Right Ascension in format parseable by astropy e.g. 00h42m30s
        :param dec: Declination in format parseable by astropy e.g. +41d12m00s

        :return: self - ready for another command
        """
        self.calc = self.pointing.point_array
        self.point_kwargs["right_ascension"] = ra
        self.point_kwargs["declination"] = dec

        print(f"Point station to ra={ra}, dec={dec}")
        return self

    def sun(self: PointingDriver) -> PointingDriver:
        """
        Generate delays and rates to track the Sun.

        :return: self - ready for another command
        """
        self.calc = self.pointing.point_to_sun
        print("Point station at the Sun.")
        return self

    def startat(self: PointingDriver, when: str, scale: str = "utc") -> PointingDriver:
        """
        Set the pointing start time.

        :param when: start time (isot type, interpretted by astropy.Time)
        :param scale: time scale, defaults to 'utc'

        :return: self - ready for another command
        """
        self.point_kwargs["pointing_time"] = Time(when, format="isot", scale=scale)
        print(f"Start pointing at {self.point_kwargs['pointing_time'].value}")
        return self

    def sequence(self: PointingDriver, count: int, interval: float) -> PointingDriver:
        """
        Generate delays for count frames at interval spacing.

        :param count: The number of pointing frames to generate
        :param interval: Time interval between pointings

        :return: self - ready for another command
        """
        print(f"Generate {count} delay sets every {interval} seconds")
        tic = time.perf_counter()

        if "pointing_time" not in self.point_kwargs:
            self.point_kwargs["pointing_time"] = Time(datetime.utcnow(), scale="utc")

        t0 = self.point_kwargs["pointing_time"]

        for i in range(count):
            self.point_kwargs["pointing_time"] = t0 + i * interval / 86400
            result = {}
            if self.calc is not None:
                self.calc(**self.point_kwargs)
                result = {
                    "frame_t": self.point_kwargs["pointing_time"],
                    "az": self.pointing._az,
                    "el": self.pointing._el,
                    "delays": self.pointing._delays,
                }
            self._results.append(result)
        toc = time.perf_counter()
        print(f"Execution time {toc - tic:0.4f} seconds")

        print(len(self._results), "frames written")
        return self

    def single(self: PointingDriver) -> PointingDriver:
        """
        Generate delays for a single pointing.

        :return: self - ready for another command
        """
        return self.sequence(1, 0)

    def pointing_job(
        self: PointingDriver,
        jobs: queue.Queue[Time],
        results: queue.Queue[Optional[dict[str, Any]]],
    ) -> None:
        """
        Worker method for pointing job processes.

        Keep get times from the jobs queue,
        processing delays for each time and output results to results queue.

        :param jobs: queue of jobs
        :param results: queue for results
        """
        while not jobs.empty():
            try:
                # Time limit on queue get in case another process got there first
                t = jobs.get(timeout=0.01)
                self.point_kwargs["pointing_time"] = t
                result = {}
                if self.calc is not None:
                    self.calc(**self.point_kwargs)
                    result = {
                        "frame_t": self.point_kwargs["pointing_time"],
                        "az": self.pointing._az,
                        "el": self.pointing._el,
                        "delays": self.pointing._delays,
                    }
                results.put(result)
            except queue.Empty:
                # Another process grabbed the job
                # This process will exit on the next loop.
                pass

        # An empty jobs queue means we can signal completion with None
        results.put(None)

    def msequence(
        self: PointingDriver, count: int, interval: float, nproc: int
    ) -> Optional[PointingDriver]:
        """
        Multiprocessing version of the sequence CLI command.

        Adding a parameter to set the number of processes.

        :param count: The number of frames to process
        :param interval: The time interval between frames
        :param nproc: The number of processes to start

        :return: self for next command
        """
        if not isinstance(nproc, int):
            print("nproc must be an integer")
            return None

        if nproc < 1:
            print("nproc must be >= 1")
            return None

        # job_queue: queue.Queue[Time] = multiprocessing.Queue()
        # results_queue: queue.Queue[Optional[dict[str, Any]]] = multiprocessing.Queue()
        job_queue: queue.Queue() = multiprocessing.Queue()  # type: ignore[valid-type]
        results_queue: queue.Queue() = multiprocessing.Queue()

        processes = [
            multiprocessing.Process(
                target=self.pointing_job, args=(job_queue, results_queue)
            )
            for x in range(nproc)
        ]

        print(f"Generate {count} delay sets every {interval} seconds - multiprocessing")
        tic = time.perf_counter()

        if "pointing_time" not in self.point_kwargs:
            self.point_kwargs["pointing_time"] = Time(datetime.utcnow(), scale="utc")

        t0 = self.point_kwargs["pointing_time"]

        for i in range(count):
            job_queue.put(t0 + i * interval / 86400)

        for p in processes:
            p.start()

        print("Processes running")

        collected = {}

        ended = 0

        # Until all processes have ended keep popping the results
        while ended < nproc:
            result = results_queue.get()
            if result is None:
                # This is the token that signals a process ended
                ended += 1
            else:
                # Otherwise we have a real result to collect
                collected[result["frame_t"]] = result

        for p in processes:
            print(f"Join process {str(p)}")
            p.join()

        print("Processes joined")

        toc = time.perf_counter()
        print(f"Execution time {toc - tic:0.4f} seconds")

        # Results could be out of order so sort them
        self._results = [collected[key] for key in sorted(collected.keys())]

        print(len(self._results), "frames written")
        return self

    def write(self: PointingDriver, filename: str) -> None:
        """
        Write the generated pointings to a file.

        :param filename: Name of output file
        """
        print(f"Writing pointing frame(s) to {filename}")
        with open(filename, "w") as outfile:
            outfile.write('"Time Stamp (isot)","Azimuth (deg)","Elevation (deg)",')
            for i in range(self.pointing.station.antennas.nof_elements):
                outfile.write(f',"Antenna {i+1:03}"')
            outfile.write("\n")
            for result in self._results:
                outfile.write(str(result["frame_t"]))
                outfile.write(",")
                outfile.write(str(result["az"]))
                outfile.write(",")
                outfile.write(str(result["el"]))
                outfile.write(",")
                delays = result["delays"].reshape(
                    (1, self.pointing.station.antennas.nof_elements)
                )
                np.savetxt(outfile, delays, delimiter=",")

    def done(self: PointingDriver) -> None:
        """Command to signal no more output required."""
        print("Done")


if __name__ == "__main__":
    fire.Fire(PointingDriver)
