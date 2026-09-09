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
#
# SRC is the tree to build, and defaults to /src, where the container has this
# repository bind-mounted.
set -e

# See build/toolchain-env.sh: it puts the crosstool prebuilt on PATH and names
# both toolchains, so this script works in a fresh shell and not only inside
# build/Dockerfile's image.  Sourced before the cd.
_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "${TOOLCHAIN_ENV:-$_here/toolchain-env.sh}"

cd "${SRC:-/src}"
: "${KSRC:=/build/linux}"
# Fatal rather than a silent fallback: the two compilers differ only in the
# .comment string, so the wrong one builds a module that looks right.
: "${TOOLCHAIN_BIN:=$VENDOR_GCC_BIN}"
toolchain_require "$TOOLCHAIN_BIN" \
    "the module carries the compiler's --with-pkgversion in .comment" \
    "sh build/build-gcc-vendor.sh"
echo "=== KSRC=$KSRC"
echo "=== cc   $("$TOOLCHAIN_TARGET-gcc" --version | head -1)  [$TOOLCHAIN_BIN]"
make clean >/dev/null 2>&1 || true
make -j"$(nproc)" \
     ARCH=arm CROSS_COMPILE="$TOOLCHAIN_TARGET-" KSRC="$KSRC" \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     "$@"
echo "=== result ==="
ls -la 8188fu.ko 2>/dev/null || { echo "NO MODULE PRODUCED"; exit 1; }
file 8188fu.ko
