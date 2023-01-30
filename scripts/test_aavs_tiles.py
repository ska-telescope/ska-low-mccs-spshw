# K8S_CHART_PARAMS="-f charts/umbrella-mccs/value_files/values_thinslice_aavs2.yaml"

import time
import tango

sr1=tango.DeviceProxy('low-mccs-spshw/subrack/0001')
sr1.adminMode=0
sr2=tango.DeviceProxy('low-mccs-spshw/subrack/0002')
sr2.adminMode=0

tpm_fqdns = [f"low-mccs-spshw/tile/{i:04d}" for i in range(1,17)]
tpms = {fqdn: tango.DeviceProxy(fqdn) for fqdn in tpm_fqdns}

sr1.On()
sr2.On()
time.sleep(2)

for tpm_index in range(1,17):
    print(f"Switching Online TPM {tpm_index}")
    tpms[f"low-mccs-spshw/tile/{tpm_index:04d}"].adminMode=0

time.sleep(2)

for tpm_index in range(1,17):
    print(f"Turning On TPM {tpm_index}")
    tpms[f"low-mccs-spshw/tile/{tpm_index:04d}"].On()

time.sleep(5)

for tpm_index in range(1,17):
    tpm = tpms[f"low-mccs-spshw/tile/{tpm_index:04d}"]
    print(f"Reading boardTemp TPM {tpm_index}: {tpm.boardTemperature}")