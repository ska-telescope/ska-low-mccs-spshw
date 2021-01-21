from __future__ import division

import functools
import socket
from builtins import str

from pyfabil.base.definitions import Device, LibraryError
from pyfabil.boards.tpm import TPM


# Helper to disallow certain function calls on unconnected tiles
def connected(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if self.tpm is None:
            self.logger.warning(
                "Cannot call function " + str(f.__name__) + " on unconnected TPM"
            )
            raise LibraryError(
                "Cannot call function " + str(f.__name__) + " on unconnected TPM"
            )
        else:
            return f(self, *args, **kwargs)

    return wrapper


class HwTile(object):
    """
    Tile hardware interface library. Streamlined and edited verson
    of the AAVS Tile object
    """
    def __init__(
        self,
        logger=None,
        ip="10.0.10.2",
        port=10000,
        lmc_ip="10.0.10.1",
        lmc_port=4660,
        sampling_rate=800e6,
    ):
        """
        HwTile initialization

        :param logger: the logger to be used by this Command. If not
                provided, then a default module logger will be used.
        :type logger: :py:class:`logging.Logger`
        :param ip: IP address of the hardware
        :type ip: str
        :param port: UCP Port address of the hardware port
        :type port: int
        :param lmc_ip: IP address of the MCCS DAQ recevier
        :type lmc_ip: str
        :param lmc_port: UCP Port address of the MCCS DAQ receiver
        :type lmc_port: int
        :param sampling_rate: ADC sampling rate
        :type sampling_rate: float
        """
        self.logger = logger
        self._lmc_port = lmc_port
        self._lmc_ip = socket.gethostbyname(lmc_ip)
        self._port = port
        self._ip = socket.gethostbyname(ip)
        self.tpm = None

        self.station_id = 0
        self.tile_id = 0

        self._sampling_rate = sampling_rate

        # Threads for continuously sending data
        self._RUNNING = 2
        self._ONCE = 1
        self._STOP = 0
        self._daq_threads = {}

        # Mapping between preadu and TPM inputs
        self.fibre_preadu_mapping = {
            0: 1,
            1: 2,
            2: 3,
            3: 4,
            7: 13,
            6: 14,
            5: 15,
            4: 16,
            8: 5,
            9: 6,
            10: 7,
            11: 8,
            15: 9,
            14: 10,
            13: 11,
            12: 12,
        }

    # ---------------------------- Main functions ------------------------------------

    def connect(self, initialise=False, simulation=False, enable_ada=False):
        """
        Connect to the hardware and loads initial configuration

        :param initialise: Initialises the TPM object
        :type initialise: bool
        :param simulation: Uses simulated hardware
        :type simulation: bool
        :param enable_ada: Enbale ADC amplifier
        :type enable_ada: bool
        """
        # Try to connect to board, if it fails then set tpm to None
        self.tpm = TPM()

        # Add plugin directory (load module locally)
        # tf = __import__("ska.low.mccs.tile.tpm_test_firmware", fromlist=[None])
        # self.tpm.add_plugin_directory(os.path.dirname(tf.__file__))

        self.tpm.connect(
            ip=self._ip,
            port=self._port,
            initialise=initialise,
            simulator=simulation,
            enable_ada=enable_ada,
            fsample=self._sampling_rate,
        )

        # Load tpm test firmware for both FPGAs (no need to load in simulation)
        if not simulation and self.tpm.is_programmed():
            self.tpm.load_plugin(
                "TpmTestFirmware",
                device=Device.FPGA_1,
                fsample=self._sampling_rate,
                logger=self.logger,
            )
            self.tpm.load_plugin(
                "TpmTestFirmware",
                device=Device.FPGA_2,
                fsample=self._sampling_rate,
                logger=self.logger,
            )
        elif not self.tpm.is_programmed():
            self.logger.warn("TPM is not programmed! No plugins loaded")

    def initialise(self, enable_ada=False, enable_test=False):
        """
        Connect and initialise
        :param enable_ada: enable adc amplifier
        :type enable_ada: bool
        :param enable_test: setup internal test signal generator instead of ADC
        :type enable_test: bool
        """

        # Connect to board
        self.connect(initialise=True, enable_ada=enable_ada)

        # Before initialing, check if TPM is programmed
        if not self.tpm.is_programmed():
            self.logger.error("Cannot initialise board which is not programmed")
            return

        # Initialise firmware plugin
        for firmware in self.tpm.tpm_test_firmware:
            firmware.initialise_firmware()

        # AAVS-only - swap polarisations due to remapping performed by preadu
        # self.tpm["fpga1.jesd204_if.regfile_pol_switch"] = 0b00001111
        # self.tpm["fpga2.jesd204_if.regfile_pol_switch"] = 0b00001111

    def program_fpgas(self, bitfile):
        """
        Program FPGA with specified firmware
        :param bitfile: Bitfile to load
        :type bitfile: str
        """
        self.connect(simulation=True)
        self.logger.info("Downloading bitfile to board")
        if self.tpm is not None:
            self.tpm.download_firmware(Device.FPGA_1, bitfile)

    @connected
    def read_cpld(self, bitfile="cpld_dump.bit"):
        """
        Read bitfile in CPLD FLASH
        :param bitfile: Bitfile where to dump CPLD firmware
        :type bitfile: str
        """
        self.logger.info("Reading bitstream from  CPLD FLASH")
        self.tpm.tpm_cpld.cpld_flash_read(bitfile)

    def get_ip(self):
        """
        Get tile IP
        :return: tile IP address
        :rtype: str
        """
        return self._ip

    @connected
    def get_temperature(self):
        """
        Read board temperature
        :return: board temperature
        :rtype: float
        """
        return self.tpm.temperature()

    @connected
    def get_voltage(self):
        """
        Read board voltage
        :return: board supply voltage
        :rtype: float
        """
        return self.tpm.voltage()

    @connected
    def get_current(self):
        """
        Read board current
        :return: board supply current
        :rtype: float
        """
        # not implemented in 1.2
        # return self.tpm.current()
        return 0.0

    @connected
    def get_adc_rms(self):
        """
        Get ADC power
        :return: ADC RMS power
        :rtype: list(float)
        """

        # If board is not programmed, return None
        if not self.tpm.is_programmed():
            return None

        # Get RMS values from board
        rms = []
        for adc_power_meter in self.tpm.adc_power_meter:
            rms.extend(adc_power_meter.get_RmsAmplitude())

        # Re-map values
        return rms

    @connected
    def get_fpga0_temperature(self):
        """
        Get FPGA0 temperature
        :return: FPGA0 temperature
        :rtype: float
        """
        if self.is_programmed():
            return self.tpm.tpm_sysmon[0].get_fpga_temperature()
        else:
            return 0

    @connected
    def get_fpga1_temperature(self):
        """
        Get FPGA0 temperature
        :return: FPGA0 temperature
        :rtype: float
        """
        if self.is_programmed():
            return self.tpm.tpm_sysmon[1].get_fpga_temperature()
        else:
            return 0

    @connected
    def get_fpga_time(self, device):
        """
        Return time from FPGA
        :param device: FPGA to get time from
        :type device: int
        :return: Internal time for FPGA
        :rtype: int
        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return self["fpga1.pps_manager.curr_time_read_val"]
        elif device == Device.FPGA_2:
            return self["fpga2.pps_manager.curr_time_read_val"]
        else:
            raise LibraryError("Invalid device specified")

    @connected
    def get_fpga_timestamp(self, device=Device.FPGA_1):
        """
        Get timestamp from FPGA
        :param device: FPGA to read timestamp from
        :type device: int
        :return: PPS time
        :rtype: int
        :raises LibraryError: Invalid value for device
        """
        if device == Device.FPGA_1:
            return self["fpga1.pps_manager.timestamp_read_val"]
        elif device == Device.FPGA_2:
            return self["fpga2.pps_manager.timestamp_read_val"]
        else:
            raise LibraryError("Invalid device specified")

    def __str__(self):
        """
        Produces list of tile information

        :return: Information string
        :rtype: str
        """
        return str(self.tpm)

    def __getitem__(self, key):
        """
        read a register using indexing syntax: value=tile['registername']

        :param key: register address, symbolic or numeric
        :type key: str
        :return: indexed register content
        :rtype: int
        """
        return self.tpm[key]

    def __setitem__(self, key, value):
        """
        Set a register to a value

        :param key: register address, symbolic or numeric
        :type key: str
        :param value: value to be written into register
        :type value: int
        """
        self.tpm[key] = value

    def __getattr__(self, name):
        if name in dir(self.tpm):
            return getattr(self.tpm, name)
        else:
            raise AttributeError(
                "'Tile' or 'TPM' object have no attribute " + str(name)
            )
