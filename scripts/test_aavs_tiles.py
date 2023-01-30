# K8S_CHART_PARAMS="-f charts/umbrella-mccs/value_files/values_thinslice_aavs2.yaml"

import time
import tango

sr1=tango.DeviceProxy('low-mccs-spshw/subrack/0001')
sr1.adminMode=0

# tpm1=tango.DeviceProxy('low-mccs-spshw/tile/0001')
# tpm2=tango.DeviceProxy('low-mccs-spshw/tile/0002')
# tpm3=tango.DeviceProxy('low-mccs-spshw/tile/0003')
# tpm4=tango.DeviceProxy('low-mccs-spshw/tile/0004')
# tpm5=tango.DeviceProxy('low-mccs-spshw/tile/0005')
# tpm6=tango.DeviceProxy('low-mccs-spshw/tile/0006')
# tpm7=tango.DeviceProxy('low-mccs-spshw/tile/0007')
# tpm8=tango.DeviceProxy('low-mccs-spshw/tile/0008')
# tpm9=tango.DeviceProxy('low-mccs-spshw/tile/0009')
# tpm10=tango.DeviceProxy('low-mccs-spshw/tile/0010')
# tpm11=tango.DeviceProxy('low-mccs-spshw/tile/0011')
# tpm12=tango.DeviceProxy('low-mccs-spshw/tile/0012')
# tpm13=tango.DeviceProxy('low-mccs-spshw/tile/0013')
# tpm14=tango.DeviceProxy('low-mccs-spshw/tile/0014')
# tpm15=tango.DeviceProxy('low-mccs-spshw/tile/0015')
# tpm16=tango.DeviceProxy('low-mccs-spshw/tile/0016')

tpm_fqdns = [f"low-mccs-spshw/tile/{i:03d}" for i in range(1,16)]
tpms = {fqdn: tango.DeviceProxy(fqdn) for fqdn in tpm_fqdns}

sr1.On()
time.sleep(2)

for tpm_index in range(1,16):
    print(f"Switching Online TPM {tpm_index}")
    tpms["low-mccs-spshw/tile/{tpm_index:03d}"].adminMode=0

time.sleep(2)

for tpm_index in range(1,16):
    print(f"Turning On TPM {tpm_index}")
    tpms["low-mccs-spshw/tile/{tpm_index:03d}"].On()

time.sleep(5)

for tpm_index in range(1,16):
    tpm = tpms["low-mccs-spshw/tile/{tpm_index:03d}"]
    print(f"Reading boardTemp TPM {tpm_index}: {tpm.boardTemperature}")