# -*- coding: utf-8 -*-
import json


class TpmSimulator:
    def __init__(self, logger):
        self.programmed = True
        # Its a simulator so programmed is True
        self.logger = logger

    def connect(
        self,
        ip=None,
        port=None,
        initialise=None,
        simulator=True,
        enable_ada=None,
        fsample=None,
    ):
        self.logger.info("TpmSimulator: connect")

    def disconnect(self):
        pass

    def is_programmed(self):
        self.logger.info(f"TpmSimulator: is_programmed {self.programmed}")
        return self.programmed

    def download_firmware(self, bitfile):
        self.logger.info("TpmSimulator: download_firmware")

    def cpld_flash_write(self, bitfile):
        self.logger.info("TpmSimulator: cpld_flash_write")

    def initialise_f2f_link(self):
        self.logger.info("TpmSimulator: initialise_f2f_link")

    def reset_test_generator(self):
        self.logger.info("TpmSimulator: reset_test_generator")

    def initialise_firmware(self):
        self.logger.info("TpmSimulator: initialise_firmware")
        pass

    def set_lmc_ip(self, lmc_ip, lmc_port):
        self.logger.info("TpmSimulator: set_lmc_ip")

    def check_ddr_initialisation(self):
        self.logger.info("TpmSimulator: initialise_f2f_link")

    def enable_test_pattern(self):
        self.logger.info("TpmSimulator: enable_test_pattern")

    def get_arp_table_status(self, n):
        self.logger.info("TpmSimulator: get_arp_table_status")
        return 0x4

    def temperature(self):
        self.logger.info("TpmSimulator: temperature")
        return 40.0

    def voltage(self):
        self.logger.info("TpmSimulator: voltage")
        return 10.5

    def current(self):
        self.logger.info("TpmSimulator: current")
        return 0.4

    def get_adc_rms(self):
        self.logger.info("TpmSimulator: get_adc_rms")
        rms = []
        for i in range(16):
            x = random.uniform(10, 35)
            y = random.uniform(x - 5, x + 5)
            rms.append(x)
            rms.append(y)

        return rms

    def get_fpga1_temperature(self):
        self.logger.info("TpmSimulator: get_fpga1_temperature")
        return 38

    def get_fpga2_temperature(self):
        self.logger.info("TpmSimulator: get_fpga2_temperature")
        return 37.5

    #     def GetRegisterList(self):
    #     def ReadRegister(self, argin):
    #     def WriteRegister(self, argin):
    #     def ReadAddress(self, argin):
    #     def WriteAddress(self, argin):
    #     def Configure40GCore(self, argin):
    #     def Get40GCoreConfiguration(self, argin):

    def set_lmc_download(
        self,
        mode,
        payload_length=1024,
        dst_ip=None,
        src_port=0xF0D0,
        dst_port=4660,
        lmc_mac=None,
    ):
        self.logger.info("TpmSimulator: set_lmc_download")

    def set_channeliser_truncation(self, argin):
        self.logger.info("TpmSimulator: set_channeliser_truncation")

    def set_beamformer_regions(self, region_array):
        self.logger.info("TpmSimulator: set_beamformer_regions")

    def initialise_beamformer(start_channel, nof_channels, is_first, is_last):
        self.logger.info("TpmSimulator: initialise_beamformer")

    def load_calibration_coefficients(self, antenna, calibration_coefs):
        self.logger.info("TpmSimulator: load_calibration_coefficients")

    def load_beam_angle(angle_coefs):
        self.logger.info("TpmSimulator: load_beam_angle")

    def load_antenna_tapering(self, tapering_coefs):
        self.logger.info("TpmSimulator: load_pointing_delay")

    def switch_calibration_bank(self, switch_time=0):
        self.logger.info("TpmSimulator: set_pointing_delay")
        print(switch_time)

    def set_pointing_delay(self, delay_array, beam_index):
        self.logger.info("TpmSimulator: set_pointing_delay")
        out = [beam_index]
        for i in range(16):
            out.append(delay_array[i][0])
            out.append(delay_array[i][1])
        print(out)

    def load_pointing_delay(self, load_time):
        self.logger.info("TpmSimulator: load_pointing_delay")
        print(load_time)

    def start_beamformer(self, start_time=0, duration=-1):
        self.logger.info("TpmSimulator: Start beamformer")
        dict = {"StartTime": start_time, "Duration": duration}
        print(json.dumps(dict))

    def stop_beamformer(self):
        self.logger.info("TpmSimulator: Stop beamformer")
        print("TpmSimulator: stop_beamformer")

    def configure_integrated_channel_data(self, integration_time=0.5):
        self.logger.info("TpmSimulator: configure_integrated_channel_data")
        print(integration_time)

    def configure_integrated_beam_data(self, integration_time=0.5):
        self.logger.info("TpmSimulator: configure_integrated_beam_data")
        print(integration_time)

    def send_raw_data(
        self, sync=False, period=0, timeout=0, timestamp=None, seconds=0.2
    ):
        self.logger.info("TpmSimulator: send_raw_data")
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
        self.logger.info("TpmSimulator: send_channelised_data")
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
        self.logger.info("TpmSimulator: send_channelised_data_continuous")
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
        self.logger.info("TpmSimulator: send_beam_data")
        dict = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def stop_data_transmission(self):
        self.logger.info("TpmSimulator: stop_data_transmission")
        print("TpmSimulator: stop_data_transmission")

    def compute_calibration_coefficients(self):
        self.logger.info("TpmSimulator: compute_calibration_coefficients")
        print("TpmSimulator: compute_calibration_coefficients")

    def start_acquisition(self, start_time=None, delay=2):
        self.logger.info("TpmSimulator:Start acquisition")
        dict = {"StartTime": start_time, "Delay": delay}
        print(json.dumps(dict))

    def set_time_delays(self, delays):
        self.logger.info("TpmSimulator: set_time_delays")
        print(delays)

    def set_csp_rounding(self, rounding):
        self.logger.info("TpmSimulator: set_csp_rounding")
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
        self.logger.info("TpmSimulator: set_lmc_integrated_download")
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
        self.logger.info("TpmSimulator: send_raw_data_synchronised")
        dict = {
            "Period": period,
            "Timeout": timeout,
            "Timestamp": timestamp,
            "Seconds": seconds,
        }
        print(json.dumps(dict))

    def current_station_beamformer_frame(self):
        # Currently this is required, not sure if it will remain so
        self.logger.info("TpmSimulator: current_station_beamformer_frame")
        return 23


#######################
# not in ICD
#######################
#     def mii_prepare_test(self, board):
#     def mii_exec_test(self, pkt_num, wait_result=True):
#     def mii_test(self, pkt_num, board, wait_result=True):
#     def mii_show_result(self):
#     def get_fpga_timestamp(self, device=Device.FPGA_1):
#     def tweak_transceivers(self):
#     def get_phase_terminal_count(self):
#     def set_phase_terminal_count(self, value):
#     def get_pps_delay(self):
#     def check_pending_data_requests(self):
#     def set_beamformer_epoch(self, epoch):
#     def current_tile_beamformer_frame(self):
#     def set_first_last_tile(self, is_first, is_last):
#     def define_spead_header(self, station_id, subarray_id, nof_antennas, ref_epoch=-1, start_time=0):
#     def beamformer_is_running(self):
#     def post_synchronisation(self):
#     def sync_fpgas(self):
#     def check_synchronization(self):
#     def check_fpga_synchronization(self):
#     def set_c2c_burst(self):
#     def synchronised_data_operation(self, seconds=0.2, timestamp=None):
#     def synchronised_beamformer_coefficients(self, timestamp=None, seconds=0.2):
#     def stop_integrated_beam_data(self):
#     def stop_integrated_channel_data(self):
#     def stop_integrated_data(self):
#     def stop_raw_data(self):
#     def stop_channelised_data(self):
#     def stop_beam_data(self):
#     def send_channelised_data_narrowband(self, frequency, round_bits, number_of_samples=128, wait_seconds=0,
#                                          timeout=0, timestamp=None, seconds=0.2):
#     def stop_channelised_data_continuous(self):
#     def schedule_stop_data_transmission(self, timeout=0):
#     def calculate_delay(current_delay, current_tc, ref_low, ref_hi):
