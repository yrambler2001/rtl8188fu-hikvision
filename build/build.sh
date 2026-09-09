#!/bin/sh
# Build 8188fu.ko inside the rtl8188fu-build image.
set -e
cd /src
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" \
     ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- KSRC=/build/linux \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     "$@"
echo "=== result ==="
ls -la 8188fu.ko 2>/dev/null || { echo "NO MODULE PRODUCED"; exit 1; }
file 8188fu.ko
