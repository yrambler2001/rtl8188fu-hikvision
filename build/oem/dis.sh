#!/bin/sh
# Annotated disassembly of a .text range of the shipped module (or any ELF):
# resolves every section-relative R_ARM_ABS32 addend to the string or symbol it
# actually points at, which is what makes the OEM literal pools readable.
#
#   sh build/oem/dis.sh 0x92220 0x94570 [file.ko] > oem.dis
set -e
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-objdump" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }
F=${3:-/orig/8188fu.ko}
D=$(dirname "$0")
arm-linux-gnueabi-objdump -d -r -j .text --start-address="$1" --stop-address="$2" "$F" \
  | python3 "$D/annot.py" "$F"
