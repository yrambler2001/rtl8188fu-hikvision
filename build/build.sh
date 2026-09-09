#!/bin/sh
# Build 8188fu.ko inside the rtl8188fu-build image.
#
# KSRC picks the kernel to build against and defaults to the kernel.org tree at
# /build/linux. rtl8188fu-build-vendor:latest (build/Dockerfile.vendor) sets
# KSRC=/build/linux-vendor in the image environment, so the same script builds
# against the Fullhan vendor tree there with no argument.
set -e
cd /src
: "${KSRC:=/build/linux}"
echo "=== KSRC=$KSRC"
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" \
     ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- KSRC="$KSRC" \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     "$@"
echo "=== result ==="
ls -la 8188fu.ko 2>/dev/null || { echo "NO MODULE PRODUCED"; exit 1; }
file 8188fu.ko
