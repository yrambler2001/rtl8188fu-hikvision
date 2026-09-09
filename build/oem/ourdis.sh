#!/bin/sh
# Disassemble ONE function out of the freshly built OEM object (/tmp/oem/*.o).
#   docker exec fuv sh /src/build/oem/ourdis.sh ez_wifi_config process_config_vars
set -e
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-objdump" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }
O=/tmp/oem/$1.o
L=$(arm-linux-gnueabi-nm -S "$O" | grep " $2\$")
S=$(echo "$L" | cut -d' ' -f1)
Z=$(echo "$L" | cut -d' ' -f2)
E=$(printf '%d\n' $((0x$S + 0x$Z)))
arm-linux-gnueabi-objdump -d -r -j .text --start-address="0x$S" --stop-address="$E" "$O"
