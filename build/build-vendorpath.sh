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
# usage: docker exec fuv sh /src/build/build-vendorpath.sh [make args]
set -e

VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
: "${SRC:=/src}"
: "${KSRC:=/build/linux-vendor}"
: "${BUILD_DATE:=Dec 25 2023}"
: "${BUILD_TIME:=20:43:27}"

echo "=== source   $SRC"
echo "=== build in $VENDOR_ROOT"
echo "=== kernel   $KSRC"

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
     ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- KSRC="$KSRC" \
     HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon" \
     USER_EXTRA_CFLAGS="$STAMP" \
     "$@"

echo "=== result ==="
ls -la "$VENDOR_ROOT/8188fu.ko"
cp "$VENDOR_ROOT/8188fu.ko" "$SRC/8188fu.ko"
echo "=== copied to $SRC/8188fu.ko"
