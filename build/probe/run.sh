#!/bin/sh
set -e
cd /probe
make -C /build/linux M=/probe ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- modules >/dev/null 2>&1
arm-linux-gnueabi-readelf -sW probe.ko | awk '$4=="OBJECT" && $8 ~ /^probe_/ {printf "  %-22s %s\n", substr($8,7), $3}' | sort
