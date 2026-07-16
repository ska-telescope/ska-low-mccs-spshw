FIRMWARE_VERSION=10.0.0
FIRMWARE_VERSION_NEW=11.0.0

download_and_extract() {
    FW_URL="https://artefact.skao.int/repository/raw-internal/ska-low-sps-tpm-fpga-$1.tar.gz"
    python3 -c "
import urllib.request, shutil, sys
shutil.copyfileobj(
    urllib.request.urlopen('$FW_URL'),
    sys.stdout.buffer,
)
" | tar -xzO ./tpm_firmware.bit > "tpm_firmware_$1.bit"
}

download_and_extract $FIRMWARE_VERSION
download_and_extract $FIRMWARE_VERSION_NEW
