# -*- coding: utf-8 -*-
import json
import time
import random
import itertools

import tango


class TpmSimulator:
    def __init__(self, logger):
        self.logger = logger
        self._programmed = False
        self._beamformer_running = False
        self._phase_terminal_count = 0
        self._fpga1_time = 0
        self._fpga2_time = 0
        self._address_map = {}
        self._forty_gb_core_list = []
        self._register0_map = {
            "test-reg1": {},
            "test-reg2": {},
            "test-reg3": {},
            "test-reg4": {},
        }
        self._register1_map = {
            "test-reg1": {},
            "test-reg2": {},
            "test-reg3": {},
            "test-reg4": {},
        }
        self._use_clock = False
        self._test_mode = False
        self._tpm_proxy = None

    def connect(
        self, initialise=None, simulation=True, enable_ada=None, testmode=False
    ):
        self.logger.debug("TpmSimulator: connect")
        self._test_mode = testmode
        try:
            self._tpm_proxy = tango.DeviceProxy("low/elt/tpmsimulator")
            self._tpm_proxy.simulate = False
        except tango.DevFailed:
            self._tpm_proxy = None
        print("TpmSimulator: connect")

    def disconnect(self):
        self.logger.debug("TpmSimulator: disconnect")
        print("TpmSimulator: disconnect")

    def get_firmware_list(self):
        self.logger.debug("TpmSimulator: get_firmware_list")
        return {
            "firmware1": {"design": "model1", "major": 2, "minor": 3},
            "firmware2": {"design": "model2", "major": 3, "minor": 7},
            "firmware3": {"design": "model3", "major": 2, "minor": 6},
        }

    def is_programmed(self):
        self.logger.debug(f"TpmSimulator: is_programmed {self._programmed}")
        return self._programmed

    def download_firmware(self, bitfile):
        self.logger.debug("TpmSimulator: download_firmware")
        self._programmed = True
        print(f"{bitfile}")

    def cpld_flash_write(self, bitfile):
        self.logger.debug("TpmSimulator: program_cpld")
        print(f"{bitfile}")

    def initialise(self):
        self.logger.debug("TpmSimulator: initialise")
        print("TpmSimulator: initialise")

    def temperature(self):
        self.logger.debug("TpmSimulator: temperature")
        if self._tpm_proxy is None:  # for unit testing
            return 36.0
        else:
            return self._tpm_proxy.temperature

    def voltage(self):
        self.logger.debug("TpmSimulator: voltage")
        if self._tpm_proxy is None:  # for unit testing
            return 4.7
        else:
            return self._tpm_proxy.voltage

    def current(self):
        self.logger.debug("TpmSimulator: current")
        if self._tpm_proxy is None:  # for unit testing
            return 0.4
        else:
            return self._tpm_proxy.current

    def get_fpga1_temperature(self):
        self.logger.debug("TpmSimulator: get_fpga1_temperature")
        if self._tpm_proxy is None:  # for unit testing
            return 38.0
        else:
            return self._tpm_proxy.fpga1_temperature

    def get_fpga2_temperature(self):
        self.logger.debug("TpmSimulator: get_fpga2_temperature")
        if self._tpm_proxy is None:  # for unit testing
            return 37.5
        else:
            return self._tpm_proxy.fpga2_temperature

    def get_adc_rms(self):
        self.logger.debug("TpmSimulator: get_adc_rms")
        rms = []
        for i in range(0, 32, 2):
            if self._test_mode:  # for unit testing
                x = float(i)
                y = float(i + 1)
            else:  # simulate real adc
                x = random.uniform(0.0, 3.0)
                y = random.uniform(0.0, 3.0)
            rms.append(x)
            rms.append(y)
        return rms

    def get_fpga1_time(self):
        self.logger.debug("TpmSimulator: get_fpga1_time")
        if self._use_clock:
            self._fpga1_time = int(time.time())
        return self._fpga1_time

    def set_fpga1_time(self, value):
        self.logger.debug("TpmSimulator: set_fpga1_time")
        self._fpga1_time = value
        if not self._use_clock:
            self._use_clock = True

    def get_fpga2_time(self):
        self.logger.debug("TpmSimulator: get_fpga2_time")
        return self._fpga2_time

    def set_fpga2_time(self, value):
        self.logger.debug("TpmSimulator: set_fpga2_time")
        self._fpga2_time = value

    def get_register_list(self):
        return list(self._register0_map.keys())

    def read_register(self, register_name, nb_read, offset, device):
        values = []
        if device == 0:
            address_map = self._register0_map.get(register_name, None)
        else:
            address_map = self._register1_map.get(register_name, None)
        if address_map is not None:
            for i in range(nb_read):
                key = str(offset + i)
                values.append(address_map.get(key, 0))
        else:
            values = []
        return values

    def write_register(self, register_name, values, offset, device):
        if device == 0:
            address_map = self._register0_map.get(register_name, None)
        else:
            address_map = self._register1_map.get(register_name, None)
        if address_map is not None:
            for i, value in enumerate(values):
                key = str(offset + i)
                address_map.update({key: value})

    def read_address(self, address, nvalues):
        values = []
        for i in range(nvalues):
            key = str(address + i)
            values.append(self._address_map.get(key, 0))
        return values

    def write_address(self, address, values):
        for i, value in enumerate(values):
            key = str(address + i)
            self._address_map.update({key: value})

    def configure_40G_core(
        self, core_id, src_mac, src_ip, src_port, dst_mac, dst_ip, dst_port
    ):
        dict = {
            "CoreID": core_id,
            "SrcMac": src_mac,
            "SrcIP": src_ip,
            "SrcPort": src_port,
            "DstMac": dst_mac,
            "DstIP": dst_ip,
            "DstPort": dst_port,
        }
        self._forty_gb_core_list.append(dict)

    def get_40G_configuration(self, core_id=-1):
        if core_id == -1:
            return self._forty_gb_core_list
        for item in self._forty_gb_core_list:
            if item.get("CoreID") == core_id:
                return item
        return None

    def set_lmc_download(
        self,
        mode,
        payload_length=1024,
        dst_ip=None,
        src_port=0xF0D0,
        dst_port=4660,
        lmc_mac=None,
    ):
        self.logger.debug("TpmSimulator: set_lmc_download")
        dict = {
            "Mode": mode,
            "PayloadLength": payload_length,
            "DstIP": dst_ip,
            "SrcPort": src_port,
            "DstPort": dst_port,
            "LmcMac": lmc_mac,
        }
        print(json.dumps(dict))

    def set_channeliser_truncation(self, array):
        self.logger.debug("TpmSimulator: set_channeliser_truncation")
        print(array.ravel())

    def set_beamformer_regions(self, regions):
        self.logger.debug("TpmSimulator: set_beamformer_regions")
        result = list(itertools.chain.from_iterable(regions))
        print(result)

    def initialise_beamformer(self, start_channel, nof_channels, is_first, is_last):
        self.logger.debug("TpmSimulator: initialise_beamformer")
        dict = {
            "StartChannel": start_channel,
            "NumTiles": nof_channels,
            "IsFirst": is_first,
            "IsLast": is_last,
        }
        print(json.dumps(dict))

    def load_calibration_coefficients(self, antenna, calibration_coeffs):
        self.logger.debug("TpmSimulator: load_calibration_coefficients")
        inp = list(itertools.chain.from_iterable(calibration_coeffs))
        out = [[v.real, v.imag] for v in inp]
        coeffs = list(itertools.chain.from_iterable(out))
        coeffs.insert(0, float(antenna))
        print(coeffs)

    def load_beam_angle(self, angle_coeffs):
        self.logger.debug("TpmSimulator: load_beam_angle")
        result = [angle_coeffs[i] for i in range(len(angle_coeffs))]
        print(result)

    def load_antenna_tapering(self, tapering_coeffs):
        self.logger.debug("TpmSimulator: load_pointing_delay")
        result = [tapering_coeffs[i] for i in range(len(tapering_coeffs))]
        print(result)

    def switch_calibration_bank(self, switch_time=0):
        self.logger.debug("TpmSimulator: set_pointing_delay")
        print(switch_time)

    def set_pointing_delay(self, delay_array, beam_index):
        self.logger.debug("TpmSimulator: set_pointing_delay")
        out = [beam_index]
        for i in range(16):
            out.append(delay_array[i][0])
            out.append(delay_array[i][1])
        print(out)

    def load_pointing_delay(self, load_time):
        self.logger.debug("TpmSimulator: load_pointing_delay")
        print(load_time)

    def start_beamformer(self, start_time=0, duration=-1):
        self.logger.debug("TpmSimulator: Start beamformer")
        self._beamformer_running = True
        dict = {"StartTime": start_time, "Duration": duration}
        print(json.dumps(dict))

    def stop_beamformer(self):
        self.logger.debug("TpmSimulator: Stop beamformer")
        self._beamformer_running = False
        print("TpmSimulator: stop_beamformer")

    def configure_integrated_channel_data(self, integration_time=0.5):
        self.logger.debug("TpmSimulator: configure_integrated_channel_data")
        print(integration_time)

    def configure_integrated_beam_data(self, integration_time=0.5):
        self.logger.debug("TpmSimulator: configure_integrated_beam_data")
        print(integration_time)

    def send_raw_data(
        self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2
    ):
        self.logger.debug("TpmSimulator: send_raw_data")
        dict = {
            "Sync": sync,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def send_channelised_data(
        self,
        number_of_samples=1024,
        first_channel=0,
        last_channel=511,
        period=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        self.logger.debug("TpmSimulator: send_channelised_data")
        dict = {
            "NSamples": number_of_samples,
            "FirstChannel": first_channel,
            "LastChannel": last_channel,
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def send_channelised_data_continuous(
        self,
        channel_id,
        number_of_samples=128,
        wait_seconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        self.logger.debug("TpmSimulator: send_channelised_data_continuous")
        dict = {
            "ChannelID": channel_id,
            "NSamples": number_of_samples,
            "WaitSeconds": wait_seconds,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def send_beam_data(self, period=0, timeout=0, timestamp=None, seconds=0.2):
        self.logger.debug("TpmSimulator: send_beam_data")
        dict = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def stop_data_transmission(self):
        self.logger.debug("TpmSimulator: stop_data_transmission")
        print("TpmSimulator: stop_data_transmission")

    def compute_calibration_coefficients(self):
        self.logger.debug("TpmSimulator: compute_calibration_coefficients")
        print("TpmSimulator: compute_calibration_coefficients")

    def start_acquisition(self, start_time=None, delay=2):
        self.logger.debug("TpmSimulator:Start acquisition")
        dict = {"StartTime": start_time, "Delay": delay}
        print(json.dumps(dict))

    def set_time_delays(self, delays):
        self.logger.debug("TpmSimulator: set_time_delays")
        result = [delays[i] for i in range(len(delays))]
        print(result)

    def set_csp_rounding(self, rounding):
        self.logger.debug("TpmSimulator: set_csp_rounding")
        print(rounding)

    def set_lmc_integrated_download(
        self,
        mode,
        channel_payload_length,
        beam_payload_length,
        dst_ip=None,
        src_port=0xF0D0,
        dst_port=4660,
        lmc_mac=None,
    ):
        self.logger.debug("TpmSimulator: set_lmc_integrated_download")
        dict = {
            "Mode": mode,
            "ChannelPayloadLength": channel_payload_length,
            "BeamPayloadLength": beam_payload_length,
            "DstIP": dst_ip,
            "SrcPort": src_port,
            "DstPort": dst_port,
            "LmcMac": lmc_mac,
        }
        print(json.dumps(dict))

    def send_raw_data_synchronised(
        self, period=0, timeout=0, timestamp=None, seconds=0.2
    ):
        self.logger.debug("TpmSimulator: send_raw_data_synchronised")
        dict = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def current_tile_beamformer_frame(self):
        # Currently this is required, not sure if it will remain so
        self.logger.debug("TpmSimulator: current_tile_beamformer_frame")
        return 23

    def beamformer_is_running(self):
        self.logger.debug("TpmSimulator: beamformer_is_running")
        return self._beamformer_running

    def check_pending_data_requests(self):
        self.logger.debug("TpmSimulator: check_pending_data_requests")
        return False

    def send_channelised_data_narrowband(
        self,
        frequency,
        round_bits,
        number_of_samples=128,
        wait_seconds=0,
        timeout=0,
        timestamp=None,
        seconds=0.2,
    ):
        self.logger.debug("TpmSimulator: send_channelised_data_narrowband")
        dict = {
            "Frequency": frequency,
            "RoundBits": round_bits,
            "NSamples": number_of_samples,
            "WaitSeconds": wait_seconds,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    #
    # The synchronisation routine for the current TPM requires that
    # the function below are accessible from the station (where station-level
    # synchronisation is performed), however I am not sure whether the routine
    # for the new TPMs will still required these
    #
    def tweak_transceivers(self):
        self.logger.debug("TpmSimulator: tweak_transceivers")
        print("TpmSimulator: tweak_transceivers")

    def get_phase_terminal_count(self):
        self.logger.debug("TpmSimulator: get_phase_terminal_count")
        return self._phase_terminal_count

    def set_phase_terminal_count(self, value):
        self.logger.debug("TpmSimulator: set_phase_terminal_count")
        self._phase_terminal_count = value

    def get_pps_delay(self):
        self.logger.debug("TpmSimulator: get_pps_delay")
        return 12

    def post_synchronisation(self):
        self.logger.debug("TpmSimulator: post_synchronisation")
        print("TpmSimulator: post_synchronisation")

    def sync_fpgas(self):
        self.logger.debug("TpmSimulator: sync_fpgas")
        print("TpmSimulator: sync_fpgas")

    @staticmethod
    def calculate_delay(current_delay, current_tc, ref_lo, ref_hi):
        dict = {
            "CurrentDelay": current_delay,
            "CurrentTC": current_tc,
            "RefLo": ref_lo,
            "RefHi": ref_hi,
        }
        print(json.dumps(dict))
