#!/bin/sh
# Build 8188fu.ko the way the vendor did: from the vendor's own absolute build
# directory, with the vendor's build timestamp.
#
# Two things about the *build environment* -- not the sources -- leak verbatim
# into .rodata.str1.1 and so block byte-exactness:
#
#   __FILE__  Two macros expand it: RT_ASSERT_RET() in core/efuse/rtw_efuse.c
#             and WARN_ON() in core/monitor/rtw_radiotap.c.  kbuild compiles an
#             out-of-tree module with an absolute $(src), so __FILE__ is the
#             absolute path of the build directory.  The shipped module carries
#                 /data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/
#                 rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/core/...
#             and nothing else path-like: no kernel-tree path leaks in.
#             So we copy the tree to exactly that path and build there.
#
#   __DATE__ / __TIME__  core/rtw_debug.c prints "build time: %s %s".  The
#             shipped module says Dec 25 2023 20:43:27.  GCC 6.5.0 predates
#             SOURCE_DATE_EPOCH support (verified: it ignores the variable), so
#             the values are pinned with -D and -Wno-builtin-macro-redefined.
#
#   .comment  A third leak is a whole section rather than a string.  GCC stamps
#             one .ident per object file, and its text is the --with-pkgversion
#             the compiler itself was configured with.  So this defaults to the
#             GCC 6.5.0 rebuilt by build/build-gcc-vendor.sh, which carries the
#             vendor's 'arm_multilib_uclibc_20200924'.  Point TOOLCHAIN_BIN at
#             /opt/gcc-6.5.0-nolibc/arm-linux-gnueabi/bin for a control build
#             with the stock kernel.org crosstool; they are otherwise the same
#             compiler, and produce identical code.
#
# usage: docker exec fuv sh /src/build/build-vendorpath.sh [make args]
set -e

# build/toolchain-env.sh puts the crosstool prebuilt on PATH - the environment
# build/Dockerfile's ENV line gives locally, and which a fresh GitHub Actions
# step does not - and names the compiler this build has to use.  Sourced from
# this script's own directory, before the cd below.
_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "${TOOLCHAIN_ENV:-$_here/toolchain-env.sh}"

VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
: "${SRC:=/src}"
: "${KSRC:=/build/linux-vendor}"
: "${BUILD_DATE:=Dec 25 2023}"
: "${BUILD_TIME:=20:43:27}"

# A missing compiler here is fatal, not a warning.  The stock crosstool would
# build this module perfectly happily and stamp "GCC: (GNU) 6.5.0" into
# .comment 159 times, so falling back to PATH does not produce a broken build -
# it produces a plausible one with the wrong SHA-256, which is worse.  The
# `cc` line below records which compiler was used: the pkgversion is in it.
: "${TOOLCHAIN_BIN:=$VENDOR_GCC_BIN}"
toolchain_require "$TOOLCHAIN_BIN" \
    "the module carries the compiler's --with-pkgversion in .comment" \
    "sh build/build-gcc-vendor.sh"

echo "=== source   $SRC"
echo "=== build in $VENDOR_ROOT"
echo "=== kernel   $KSRC"
echo "=== cc       $("$TOOLCHAIN_TARGET-gcc" --version | head -1)  [$TOOLCHAIN_BIN]"

rm -rf "$VENDOR_ROOT"
mkdir -p "$VENDOR_ROOT"
tar -C "$SRC" --exclude=.git --exclude='*.o' --exclude='*.ko' --exclude='.*.cmd' \
    --exclude='.tmp_versions' --exclude='*.mod.c' --exclude=Module.symvers \
    --exclude=modules.order -cf - . | tar -C "$VENDOR_ROOT" -xf -

cd "$VENDOR_ROOT"
make clean >/dev/null 2>&1 || true

# The single quotes survive make and are removed by the shell that runs the
# compile line, so GCC sees  -D__DATE__="Dec 25 2023"  as one argument.
STAMP="-Wno-builtin-macro-redefined -D__DATE__='\"$BUILD_DATE\"' -D__TIME__='\"$BUILD_TIME\"'"

make -j"$(nproc)" \
     ARCH=arm CROSS_COMPILE="$TOOLCHAIN_TARGET-" KSRC="$KSRC" \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     USER_EXTRA_CFLAGS="$STAMP" \
     "$@"

echo "=== result ==="
ls -la "$VENDOR_ROOT/8188fu.ko"
cp "$VENDOR_ROOT/8188fu.ko" "$SRC/8188fu.ko"
echo "=== copied to $SRC/8188fu.ko"
