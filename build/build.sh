#!/bin/sh
# Build 8188fu.ko inside the rtl8188fu-build image.
#
# KSRC picks the kernel to build against and defaults to the kernel.org tree at
# /build/linux. rtl8188fu-build-vendor:latest (build/Dockerfile.vendor) sets
# KSRC=/build/linux-vendor in the image environment, so the same script builds
# against the Fullhan vendor tree there with no argument.
#
# TOOLCHAIN_BIN picks the compiler and defaults to the GCC 6.5.0 rebuilt by
# build/build-gcc-vendor.sh, which carries the vendor's --with-pkgversion; set it
# to /opt/gcc-6.5.0-nolibc/arm-linux-gnueabi/bin for the stock kernel.org
# crosstool. The two are the same compiler apart from that string.
set -e
cd /src
: "${KSRC:=/build/linux}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
if [ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ]; then
    PATH="$TOOLCHAIN_BIN:$PATH"
    export PATH
fi
echo "=== KSRC=$KSRC"
echo "=== cc   $(arm-linux-gnueabi-gcc --version | head -1)"
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" \
     ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- KSRC="$KSRC" \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     "$@"
echo "=== result ==="
ls -la 8188fu.ko 2>/dev/null || { echo "NO MODULE PRODUCED"; exit 1; }
file 8188fu.ko
