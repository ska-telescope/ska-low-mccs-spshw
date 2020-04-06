# -*- coding: utf-8 -*-
class TpmSimulator:
    def __init__(self, logger):
        self.programmed = False
        self.logger = logger

    def connect(
        self,
        ip=None,
        port=None,
        initialise=None,
        simulator=None,
        enable_ada=None,
        fsample=None,
    ):
        self.logger.info("TpmSimulator: connect")
        if simulator:
            self.programmed = True

    def add_plugin_directory(self, dir):
        pass

    def load_plugin(self, firmware, sampling_rate):
        self.logger.info("TpmSimulator: load plugin")
        # load_plugin(firmware, device=Device.FPGA_1, fsample=sampling_rate)
        # load_plugin(firmware, device=Device.FPGA_2, fsample=sampling_rate)
        self.programmed = True

    def is_programmed(self):
        self.logger.info(f"TpmSimulator: is_programmed {self.programmed}")
        return self.programmed

    def download_firmware(self, bitfile):
        self.logger.info("TpmSimulator: download_firmware")
        # download_firmware(Device.FPGA_1, bitfile)

    def cpld_flash_write(self, bitfile):
        self.logger.info("TpmSimulator: cpld_flash_write")
        # tpm_cpld.cpld_flash_write(bitfile)

    def initialise_f2f_link(self):
        self.logger.info("TpmSimulator: initialise_f2f_link")
        # tpm_f2f[0].initialise_core("fpga2->fpga1")
        # tpm_f2f[1].initialise_core("fpga1->fpga2")

    def reset_test_generator(self):
        self.logger.info("TpmSimulator: reset_test_generator")
        # test_generator[0].channel_select(0x0000)
        # test_generator[1].channel_select(0x0000)
        # test_generator[0].disable_prdg()
        # test_generator[1].disable_prdg()

    def initialise_firmware(self):
        self.logger.info("TpmSimulator: initialise_firmware")
        # for firmware in tpm_test_firmware:
        #    firmware.initialise_firmware()
        pass

    def set_lmc_ip(self, lmc_ip, lmc_port):
        self.logger.info("TpmSimulator: set_lmc_ip")

    def check_ddr_initialisation(self):
        self.logger.info("TpmSimulator: initialise_f2f_link")
        # for firmware in tpm_test_firmware:
        #    firmware.check_ddr_initialisation()
        pass

    def enable_test_pattern(self):
        self.logger.info("TpmSimulator: enable_test_pattern")
        # for generator in self.tpm.test_generator:
        #    generator.set_tone(0, old_div(72 * self._sampling_rate, 1024), 0.0)
        #    generator.enable_prdg(0.4)
        #    generator.channel_select(0xFFFF)

    def get_arp_table_status(self, n):
        self.logger.info("TpmSimulator: get_arp_table_status")
        # return tpm_10g_core[n].get_arp_table_status(0, silent_mode=True)
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
        # for adc_power_meter in self.tpm.adc_power_meter:
        #    rms.extend(adc_power_meter.get_RmsAmplitude())

        for i in range(16):
            x = random.uniform(10, 35)
            y = random.uniform(x - 5, x + 5)
            rms.append(x)
            rms.append(y)

        return rms

    def get_fpga1_temperature(self):
        self.logger.info("TpmSimulator: get_fpga1_temperature")
        # return tpm_sysmon[0].get_fpga_temperature()
        return 38

    def get_fpga2_temperature(self):
        self.logger.info("TpmSimulator: get_fpga2_temperature")
        # return tpm_sysmon[1].get_fpga_temperature()
        return 37.5
