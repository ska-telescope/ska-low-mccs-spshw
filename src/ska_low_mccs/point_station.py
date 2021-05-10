#! /usr/bin/python

import logging
import os
import time
from typing import Sequence
import warnings
from builtins import object
from builtins import range
from datetime import datetime
import functools

from multiprocessing import Queue, Process

import fire

import numpy as np
from astropy import constants
from astropy.coordinates import Angle, AltAz, SkyCoord, EarthLocation, get_sun
from astropy.time import TimeDelta
from astropy.time.core import Time
from astropy.utils.exceptions import AstropyWarning

# from pyaavs import station
# import pyaavs.logger

# try:
#     import aavs_calibration.common as calib_utils
# except ImportError:
#     logging.debug("Could not load calibration database. Pointing cannot be performed")

warnings.simplefilter("ignore", category=AstropyWarning)

__author__ = "Alessio Magro"

antennas_per_tile = 16


class AntennaInformation(object):
    """
    Class for holding a station's antenna information.
    """

    def __init__(self):
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
        self.latitude = None
        self.longitude = None
        self.ellipsoidalheight = None
        self.antennas = AntennaInformation()

    def loaddisplacements(self, antennafile):
        """
        Proxy to the method in the associated AntennaInformation object.

        :param txtfile: displacements file
        :type txtfile: String
        """
        self.antennas.loaddisplacements(antennafile)

    def setlocation(self, latitude, longitude, ellipsoidalheight):
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
        :return: The (delay,delay rate) tuple for each antenna
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
        :param right_ascension: Right ascension of source (astropy angle, or string that can be converted to angle)
        :param declination: Declination of source (astropy angle, or string that can be converted to angle)
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

    # def download_delays(self):
    #     """ Download generated delays to station """
    #     if self._delays is None:
    #         logging.error("Delays have not been computed yet")
    #         return

    #     if self.station is None:
    #         logging.error("Station configuration required to download delays")
    #         return

    #     # Connect to tiles in station
    #     try:
    #         # TODO: out to tiles
    #         pass
    #         # station.load_configuration_file(self._station_config)
    #         # aavs_station = station.Station(station.configuration)
    #         # aavs_station.connect()

    #         # # Form TPM-compatible delays
    #         # tpm_delays = np.zeros((self._nof_antennas, 2))
    #         # tpm_delays[:, 0] = self._delays
    #         # tpm_delays[:, 1] = self._delay_rate

    #         # # Download to tiles
    #         # t0 = time.time()
    #         # for i, tile in enumerate(aavs_station.tiles):
    #         #     tile.set_pointing_delay(tpm_delays[i * antennas_per_tile: (i + 1) * antennas_per_tile], 0)
    #         # t1 = time.time()
    #         # logging.info("Downloaded delays to tiles in {0:.2}s".format(t1 - t0))

    #         # # Load downloaded delays
    #         # aavs_station.load_pointing_delay(2048)

    #     except Exception as e:
    #         logging.error("Could not configure or connect to station, not loading delays ({})".format(e))

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

        :param right_ascension: Right ascension of source (in astropy Angle on string which can be converted to Angle)
        :param declination: Declination of source (in astropy Angle on string which can be converted to Angle)
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


class PointingDriver(object):
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
            # print (f'calc frame at {self.point_kwargs["pointing_time"].value}')
            # print(f'Type {type(self.point_kwargs["pointing_time"])}')
            self.calc(**self.point_kwargs)
            result = {
                "frame_t": str(self.point_kwargs["pointing_time"]),
                "az": self.pointing._az,
                "el": self.pointing._el,
                "delays": self.pointing._delays,
            }
            self._results.append(result)
        toc = time.perf_counter()
        print(f"Execution time {toc - tic:0.4f} seconds")
        # print(self.pointing._delays)
        print(len(self._results), "frames written")
        return self

    def single(self):
        """
        Generate delays for a single pointing.

        :return: self - ready for another command
        :rtype: pointing_driver
        """
        return self.sequence(1, 0)

    def pointing_job (self, jobs, results):

        while True:
            t = jobs.get()

            print (f"pointing_job({str(t)})")

            if t:
                self.point_kwargs["pointing_time"] = t
                self.calc(**self.point_kwargs)
                result = {
                    "frame_t": str(self.point_kwargs["pointing_time"]),
                    "az": self.pointing._az,
                    "el": self.pointing._el,
                    "delays": self.pointing._delays,
                }
                results.put(result)
            else:
                print("End of jobs")
                return

    def msequence (self, count, interval, nproc):

        job_queue = Queue()
        results_queue = Queue()

        processes = [Process(
            target=self.pointing_job,
            args=(job_queue,results_queue),
            daemon=True
            ) for x in range(nproc)]

        print(f"Generate {count} delay sets every {interval} seconds - multiprocessing")
        tic = time.perf_counter()

        if "pointing_time" not in self.point_kwargs:
            self.point_kwargs["pointing_time"] = Time(datetime.utcnow(), scale="utc")

        t0 = self.point_kwargs["pointing_time"]

        for i in range(count):
            job_queue.put(t0 + i * interval / 86400)

        job_queue.put(None)

        print ("job_queue loaded")

        for p in processes:
            print (f"Start process {str(p)}")
            p.start()

        print ("Processes running")

        for p in processes:
            print (f"Join process {str(p)}")
            p.join()

        print ("Processes joined")

        toc = time.perf_counter()
        print(f"Execution time {toc - tic:0.4f} seconds")

        while not results_queue.empty():
            self._results.append(results_queue.get())

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
                outfile.write(result["frame_t"])
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

# if __name__ == "__main__":
#     from optparse import OptionParser
#     from sys import argv, stdout

#     parser = OptionParser(usage="usage: %point_station [options]")
#     parser.add_option("--station", action="store", dest="station", default="AAVS1",
#                       help="Station identifier (default: AAVS1)")
#     parser.add_option("--config", action="store", dest="config",
#                       default=None, help="Station configuration file to use")
#     parser.add_option("--ra", action="store", dest="ra", type=str,
#                       default="0", help="RA [default: 0]")
#     parser.add_option("--dec", action="store", dest="dec", type=str,
#                       default="0", help="DEC [default: 0]")
#     parser.add_option("--static", action="store_true", dest="static", default=False,
#                       help="Generate static beams based on theta and phi arguments [default: False]")
#     parser.add_option("--altitude", action="store", dest="alt", type=str,
#                       default="0", help="Altitude [default: 0]")
#     parser.add_option("--azimuth", action="store", dest="az", type=str,
#                       default="0", help="Azimuth [default: 0]")
#     parser.add_option("--sun", action="store_true", dest="sun",
#                       default=False, help="Point to sun [default: False]")
#     parser.add_option("--time", action="store", dest="time", default="now",
#                       help="Time at which to generate pointing delays.
#                       Format: dd/mm/yyyy_hh:mm [default: now]")

#     (opts, args) = parser.parse_args(argv[1:])

#     # Check if a configuration file was defined
#     if opts.config is None or not os.path.exists(opts.config):
#         # TODO: Output to logger
#         # log.error("A station configuration file is required, exiting")
#         exit()

#     # Parse time
#     pointing_time = datetime.utcnow()
#     if opts.time != "now":
#         try:
#             pointing_time = datetime.strptime(opts.starttime, "%d/%m/%Y_%H:%M")
#         except:
#             logging.info("Could not parse pointing time. Format should be dd/mm/yyyy_hh:mm")
#             exit()

#     # Generate pointing object
#     pointing = Pointing(opts.station, opts.config)

#     # Generate delay and delay rates
#     if opts.sun:
#         logging.info("Pointing to the sun")
#         pointing.point_to_sun(pointing_time)
#     elif opts.static:
#         opts.alt, opts.az = Angle(opts.alt), Angle(opts.az)
#         logging.info("Pointing to ALT {}, AZ {}".format(opts.alt, opts.az))
#         pointing.point_array_static(opts.alt, opts.az)
#     else:
#         opts.ra, opts.dec = Angle(opts.ra), Angle(opts.dec)
#         logging.info("Pointing to RA {}, DEC {}".format(opts.ra, opts.dec))
#         pointing.point_array(opts.ra, opts.dec,  pointing_time=pointing_time, delta_time=0)

#     # Download coefficients to station
#     pointing.download_delays()
