#!/bin/sh
# Print "<function name> <DECL_UID>" for every __func__/__FUNCTION__ array in a
# freshly compiled driver object -- the DECL_UID uniquifiers the shipped module
# pins in .strtab.  Usage: uidfn.sh os_dep/linux/ez_sc.c
set -e
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
PATH="$TOOLCHAIN_BIN:$PATH"; export PATH
sh /src/build/oem/uidprobe.sh "$1" >/dev/null 2>&1 || true
B=$(basename "$1" .c)
arm-linux-gnueabi-objdump -t -j .rodata "/tmp/uid/$B.o" 2>/dev/null |
  awk '/__func__\.|__FUNCTION__\./ {print $1, $NF}' |
  while read a n; do
    s=$(arm-linux-gnueabi-objdump -s -j .rodata --start-address=0x$a --stop-address=$((0x$a+40)) "/tmp/uid/$B.o" 2>/dev/null |
        sed -n 's/^ *[0-9a-f]*  \([0-9a-f ]*\)  \(.*\)$/\2/p' | tr -d '\n' | sed 's/\..*//')
    echo "$n $s"
  done | sed 's/\.\([0-9]*\) /.\1 /' | sort -t. -k2 -n
