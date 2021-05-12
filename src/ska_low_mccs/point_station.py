# -*- coding: utf-8 -*-
#
# This file is part of the SKA Low MCCS project
#
#
#
# Distributed under the terms of the GPL license.
# See LICENSE.txt for more info.

"""
MCCS pointing calculation prototype.

This is originally from the AAVS code.
"""
import logging
import time

import warnings
from builtins import object
from builtins import range
from datetime import datetime

from multiprocessing import Queue, Process
from multiprocessing.queues import Empty

import fire

import numpy as np
from astropy import constants
from astropy.coordinates import Angle, AltAz, SkyCoord, EarthLocation, get_sun
from astropy.time import TimeDelta
from astropy.time.core import Time
from astropy.utils.exceptions import AstropyWarning

warnings.simplefilter("ignore", category=AstropyWarning)

__author__ = "Alessio Magro"

antennas_per_tile = 16


class AntennaInformation(object):
    """
    Class for holding a station's antenna information.
    """

    def __init__(self):
        """
        Initialize AntennaInformation object with default 256 elements
        but no displacements, &c.
        """
        self.nof_elements = 256
        self.xyz = None
        self.elementid = None
        self.tpmid = None

    def loaddisplacements(self, txtfile):
        """
        Load antenna displacements from a text file.

        The file is formatted as per AAVS_loc_italia_190429.txt
        This 4 float-formatted columns separated by spaces.
        The column order is - Element x y TPM
        The header line is skipped.
        x and y units are metres

        :param txtfile: displacements file
        :type txtfile: String
        """
        aavs2 = np.loadtxt(
            txtfile,
            skiprows=1,
        )
        print(aavs2)
        print(aavs2.shape)
        self.nof_elements = aavs2.shape[0]
        self.xyz = np.append(aavs2[:, 1:3], np.zeros((self.nof_elements, 1)), axis=1)
        self.elementid = aavs2[:, 0].astype(int)
        self.tpmid = aavs2[:, 3].astype(int)


class StationInformation(object):
    """
    Class for holding information about a station.
    """

    def __init__(self):
        """
        Initialize StationInformation object with no location data and
        default AntennaInformation object (which will have no element
        diplacement data)
        """
        self.latitude = None
        self.longitude = None
        self.ellipsoidalheight = None
        self.antennas = AntennaInformation()

    def loaddisplacements(self, antennafile):
        """
        Proxy to the method in the associated AntennaInformation object.

        :param antennafile: displacements file
        :type antennafile: String
        """
        self.antennas.loaddisplacements(antennafile)

    def setlocation(self, latitude, longitude, ellipsoidalheight):
        """
        Set the location data for this station.

        :param latitude: the latitude of the station (WGS84)
        :type latitude: float
        :param longitude: the longitude of the station (WGS84)
        :type longitude: float
        :param ellipsoidalheight: the ellipsoidal height of the station
        :type ellipsoidalheight: float
        """
        assert latitude <= 90.0 and latitude >= -90.0
        self.latitude = latitude
        assert longitude <= 180.0 and longitude >= -180.0
        self.longitude = longitude
        # Probably this range could be narrowed
        assert ellipsoidalheight >= -107.0 and ellipsoidalheight <= 8870.5
        self.ellipsoidalheight = ellipsoidalheight


class Pointing(object):
    """
    Helper class for generating beamforming coefficients.
    """

    # def __init__(self, station_identifier, station_config=None):
    def __init__(self, station_info):
        # """ Pointing class, generates delay and delay rates to be downloaded to TPMs
        # :param station_identifier: Calibration database station identifier
        # :param station_config: Path to station configuration file
        # """
        """
        Pointing class, generates delay and delay rates to be downloaded
        to TPMs.

        :param station_info: Basic information for station location and antenna displacements
        """

        # Store arguments
        # self._station_id = station_identifier
        # self._station_config = station_config
        self.station = station_info

        # Get station location
        # info = calib_utils.get_station_information(self._station_id)
        self._longitude = self.station.longitude
        self._latitude = self.station.latitude
        self._height = self.station.ellipsoidalheight

        # Initial az/el pointing
        self._az = 0.0
        self._el = 0.0

        self._antennas = self.station.antennas
        self._nof_antennas = self._antennas.nof_elements

        # Grab antenna locations and create displacement vectors
        # _, x, y = calib_utils.get_antenna_positions(self._station_id)

        # self._displacements = np.full([self._nof_antennas, 3], np.nan)
        # for i in range(self._nof_antennas):
        #     self._displacements[i, :] = x[i], y[i], 0

        # self._displacements = self._antennas.xyz

        # Get reference antenna location
        self._reference_antenna_loc = EarthLocation.from_geodetic(
            self._longitude, self._latitude, height=self._height, ellipsoid="WGS84"
        )

        # Placeholder for delays and flag for below horizon
        self._below_horizon = False
        self._delays = None
        self._delay_rate = None

    # -------------------------------- POINTING FUNCTIONS -------------------------------------
    def point_to_sun(self, pointing_time=None):
        """
        Generate delays to point towards the sun for the given time.

        :param pointing_time: Time at which delays should be generated
        """

        # If no time is specified, get current time
        if pointing_time is None:
            pointing_time = Time(datetime.utcnow(), scale="utc")
        # else:
        #     pointing_time = Time(pointing_time, scale='utc')

        # print(f"Pointing time is {pointing_time.value}")

        # Get sun position in RA, DEC and convert to Alz, Az in telescope reference frame
        sun_position = get_sun(pointing_time)
        alt, az = self._ra_dec_to_alt_az(
            sun_position.ra,
            sun_position.dec,
            pointing_time,
            self._reference_antenna_loc,
        )

        # Compute delays
        self.point_array_static(alt, az)

    def point_array_static(self, altitude, azimuth, pointing_time=None):
        """
        Calculate the delay given the altitude and azimuth coordinates
        of a sky object as astropy angles.

        :param altitude: altitude coordinates of a sky object as astropy angle
        :param azimuth: azimuth coordinates of a sky object as astropy angles
        :param pointing_time: the time at which the pointing will be active
        """

        _ = pointing_time

        # Type conversions if required
        altitude = self.convert_to_astropy_angle(altitude)
        azimuth = self.convert_to_astropy_angle(azimuth)

        self._az = azimuth.value
        self._el = altitude.value

        # Set above horizon flag
        if altitude < 0.0:
            self._below_horizon = True
        else:
            self._below_horizon = False

        # Compute the delays
        self._delays = self._delays_from_altitude_azimuth(altitude.rad, azimuth.rad)
        self._delay_rate = self._delays * 0

    def point_array(
        self, right_ascension, declination, pointing_time=None, delta_time=1.0
    ):
        """Calculate the phase shift between two antennas which is given by the phase constant (2 * pi / wavelength)
        multiplied by the projection of the baseline vector onto the plane wave arrival vector
        :param right_ascension: Right ascension of source - astropy Angle / string convertable to Angle
        :param declination: Declination of source - astropy Angle / string convertable to Angle
        :param pointing_time: Time of observation (in format astropy time)
        :param delta_time: Delta timing for calculating delay rate
        :return: The (delay,delay rate) tuple for each antenna
        """

        # If no time is specified, get current time
        if pointing_time is None:
            pointing_time = Time(datetime.utcnow(), scale="utc")
        # else:
        #     pointing_time = Time(pointing_time, scale='utc')

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

        # print(f"Will point to az={az}, el={alt}  ")
        # If required source is not above horizon, generate zeros
        if alt < 0.0:
            self._delays = np.zeros(self._nof_antennas)
            self._delay_rate = np.zeros(self._nof_antennas)
            self._below_horizon = True
            return

        # Generate delays from calculated altitude and azimuth
        self.point_array_static(altitude=alt, azimuth=az)

        # Calculate required delay rate
        if delta_time == 0:
            self._delay_rate = self._delays * 0
        else:
            pointing_time = pointing_time + TimeDelta(delta_time, format="sec")
            alt, az = self._ra_dec_to_alt_az(
                right_ascension,
                declination,
                Time(pointing_time),
                self._reference_antenna_loc,
            )
            # self._delay_rate = self.point_array_static(alt, az) - self._delays
            self._delay_rate = (
                self._delays_from_altitude_azimuth(alt.rad, az.rad) - self._delays
            )

        # Set above horizon flag
        self._below_horizon = False

    def get_pointing_coefficients(self, start_channel, nof_channels):
        """
        Get complex pointing coefficients from generated delays.

        :param start_channel: Start channel index
        :param nof_channels: Number of channels starting with start_channel
        """

        if self._delays is None:
            logging.error("No pointing delays generated")
            return

        # If below horizon flat is set, return 0s
        if self._below_horizon:
            return np.zeros((self._nof_antennas, nof_channels), dtype=np.complex)

        # Compute frequency range
        channel_bandwidth = 400e6 / 512.0
        frequencies = np.array(
            [
                start_channel * channel_bandwidth + i * channel_bandwidth
                for i in range(nof_channels)
            ]
        )

        # Generate coefficients
        coefficients = np.zeros((self._nof_antennas, nof_channels), dtype=np.complex)
        for i in range(nof_channels):
            delays = 2.0 * np.pi * frequencies[i] * self._delays
            coefficients[:, i] = np.cos(delays) + 1j * np.sin(delays)

        # All done, return coefficients
        return coefficients

    def _delays_from_altitude_azimuth(self, altitude, azimuth):
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
        # path_length = np.dot(scale, self._displacements.T)
        path_length = np.dot(scale, self._antennas.xyz.T)

        # Return frequency-independent geometric delays
        return np.multiply(1.0 / constants.c.value, path_length)

    @staticmethod
    def _ra_dec_to_alt_az(right_ascension, declination, time, location):
        """
        Calculate the altitude and azimuth coordinates of a sky object
        from right ascension and declination and time.

        :param right_ascension: Right ascension of source - astropy Angle / string convertable to Angle
        :param declination: Declination of source - astropy Angle / string convertable to Angle
        :param time: Time of observation (as astropy Time")
        :param location: astropy EarthLocation
        :return: Array containing altitude and azimuth of source as astropy angle
        """

        # Initialise SkyCoord object using the default frame (ICRS) and convert to horizontal
        # coordinates (altitude/azimuth) from the antenna's perspective.
        sky_coordinates = SkyCoord(ra=right_ascension, dec=declination, unit="deg")
        altaz = sky_coordinates.transform_to(AltAz(obstime=time, location=location))

        return altaz.alt, altaz.az

    @staticmethod
    def convert_to_astropy_angle(angle):
        """
        Convert a number or string to an Astropy angle.

        :param angle: angle
        :type angle: Float
        :return: converted angle
        :rtype: Angle
        """
        if type(angle) is not Angle:
            return Angle(angle)
        return angle

    def is_above_horizon(self, right_ascension, declination, pointing_time):
        """
        Determine whether the target is above the horizon, at the
        specified time for the reference antenna.

        :param right_ascension: The right ascension of the target as a astropy angle
        :param declination: The declination of the target as an astropy angle.
        :param pointing_time: The observation time as an astropy Time.
        :return: True if the target coordinates are above the horizon at the specified time, false otherwise.
        """
        alt, _ = self._ra_dec_to_alt_az(
            Angle(right_ascension),
            Angle(declination),
            Time(pointing_time),
            self._reference_antenna_loc,
        )

        return alt > 0.0


class PointingDriver:
    """
    The class provides the Fire CLI interface to the Pointing class.

    The methods of the class provide the commands for the CLI.
    """

    def __init__(self):
        """
        Initialize point_driver object with a default StationInformation
        setup for array centre and create the Pointing object.

        Otherwise leave everything at None.
        """
        # def __init__(self, dispfile=None, outfile=None, statpos=None):
        self.dispfile = None
        # self.starttime = None
        self.calc = None
        self.point_kwargs = {}
        station = StationInformation()
        station.setlocation(-26.82472208, 116.7644482, 346.36)
        self.pointing = Pointing(station)
        self._results = []

    def statpos(self, lat, lon, height):
        """
        Command to set the station reference position.

        :param lat: latitude (WGS84, decimal degrees north)
        :type lat: Float
        :param lon: longitude (WGS84, decimal degrees east)
        :type lon: Float
        :param height: Ellipsoidal height (m)
        :type height: Float
        :return: self - ready for another command
        :rtype: pointing_driver
        """
        self.pointing.station.setlocation(lat, lon, height)
        # self.pointing = Pointing(self.station)
        return self

    def displacements(self, file):
        """
        Load the station antenna displacements from file.

        :param file: displacements file
        :type file: String
        :return: self - ready for another command
        :rtype: pointing_driver
        """
        self.pointing.station.loaddisplacements(file)
        print(f"xyz array shape: {self.pointing.station.antennas.xyz.shape}")
        return self

    def azel(self, az, el):
        """
        Generate static delays to point to the given azimuth and
        elevation.

        :param az: Azimuth in format parseable by astropy e.g. 180d
        :type az: String
        :param el: Elevation in format parseable by astropy e.g. 45d
        :type el: String
        :return: self - ready for another command
        :rtype: pointing_driver
        """

        self.calc = self.pointing.point_array_static
        self.point_kwargs["altitude"] = el
        self.point_kwargs["azimuth"] = az

        print(f"Point station to az={az}, el={el}")
        return self

    def radec(self, ra, dec):
        """
        Generate delays and rates to track the given Right Ascension and
        Declination.

        :param ra: Right Ascension in format parseable by astropy e.g. 00h42m30s
        :type ra: String
        :param dec: Declination in format parseable by astropy e.g. +41d12m00s
        :type dec: String
        :return: self - ready for another command
        :rtype: pointing_driver
        """
        self.calc = self.pointing.point_array
        self.point_kwargs["right_ascension"] = ra
        self.point_kwargs["declination"] = dec

        print(f"Point station to ra={ra}, dec={dec}")
        return self

    def sun(self):
        """
        Generate delays and rates to track the Sun.

        :return: self - ready for another command
        :rtype: pointing_driver
        """
        self.calc = self.pointing.point_to_sun
        print("Point station at the Sun.")
        return self

    def startat(self, when, scale="utc"):
        """
        Set the pointing start time.

        :param when: start time (isot type, interpretted by astropy.Time)
        :type when: String
        :param scale: time scale, defaults to 'utc'
        :type scale: str, optional
        :return: self - ready for another command
        :rtype: pointing_driver
        """
        self.point_kwargs["pointing_time"] = Time(when, format="isot", scale=scale)
        print(f"Start pointing at {self.point_kwargs['pointing_time'].value}")
        return self

    def sequence(self, count, interval):
        """
        Generate delays for count frames at interval spacing.

        :param count: The number of pointing frames to generate
        :type count: Int
        :param interval: Time interval between pointings
        :type interval: Float
        :return: self - ready for another command
        :rtype: pointing_driver
        """
        print(f"Generate {count} delay sets every {interval} seconds")
        tic = time.perf_counter()

        if "pointing_time" not in self.point_kwargs:
            self.point_kwargs["pointing_time"] = Time(datetime.utcnow(), scale="utc")

        t0 = self.point_kwargs["pointing_time"]

        for i in range(count):
            self.point_kwargs["pointing_time"] = t0 + i * interval / 86400
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

    def single(self):
        """
        Generate delays for a single pointing.

        :return: self - ready for another command
        :rtype: pointing_driver
        """
        return self.sequence(1, 0)

    def pointing_job(self, jobs, results):
        """
        Worker method for pointing job processes. Keep get times from
        the jobs queue, processing delays for each time and output
        results to results queue.

        :param jobs: queue of jobs
        :type jobs: multiprocessing.queue
        :param results: queue for results
        :type results: multiprocessing.queue
        """

        while not jobs.empty():
            try:
                # Time limit on queue get in case another process got there first
                t = jobs.get(timeout=0.01)
                self.point_kwargs["pointing_time"] = t
                self.calc(**self.point_kwargs)
                result = {
                    "frame_t": self.point_kwargs["pointing_time"],
                    "az": self.pointing._az,
                    "el": self.pointing._el,
                    "delays": self.pointing._delays,
                }
                results.put(result)
            except Empty:
                # Another process grabbed the job
                # This process will exit on the next loop.
                pass

        # An empty jobs queue means we can signal completion with None
        results.put(None)

    def msequence(self, count, interval, nproc):
        """
        Multiprocessing version of the sequence CLI command, adding a
        parameter to set the number of processes.

        :param count: The number of frames to process
        :type count: int
        :param interval: The time interval between frames
        :type interval: double
        :param nproc: The number of processes to start
        :type nproc: int
        :return: self for next command
        :rtype: PointingDriver
        """

        if not isinstance(nproc, int):
            print("nproc must be an integer")
            return

        if nproc < 1:
            print("nproc must be >= 1")
            return

        job_queue = Queue()
        results_queue = Queue()

        processes = [
            Process(
                target=self.pointing_job,
                args=(job_queue, results_queue),
                # daemon=True
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

    def write(self, filename):
        """
        Write the generated pointings to a file.

        :param filename: Name of output file
        :type filename: String
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
                # print(result["frame_t"])
                delays = result["delays"].reshape(
                    (1, self.pointing.station.antennas.nof_elements)
                )
                np.savetxt(outfile, delays, delimiter=",")

    def done(self):
        """
        Command to signal no more output required.
        """
        print("Done")


if __name__ == "__main__":
    fire.Fire(PointingDriver)
