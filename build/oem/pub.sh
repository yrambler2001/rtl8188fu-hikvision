#!/bin/sh
# Compile ONE public driver source file and score named functions in it against
# the shipped module -- the same loop as build/oem/run.sh, for the four public
# functions the OEM patch distorts.
#
#   docker exec fuv sh /src/build/oem/pub.sh os_dep/linux/ioctl_linux.c rtw_ioctl [-v]
set -e
: "${KSRC:=/build/linux-vendor}"
: "${SRC:=/src}"
: "${SHIPPED:=/orig/8188fu.ko}"
: "${OUT:=/tmp/oem}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }

CFILE=$1; FN=$2; shift 2
EXTRA="$*"
BASE=$(basename "$CFILE" .c)
# Compile flags come from the last real build's .rtw_mlme.o.cmd, so they track
# the Makefile automatically.  Prefer the vendor-path build (build-vendorpath.sh)
# over a plain /src build, because only that one carries -DCONFIG_EZ_WIFI.
VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
for c in "$VENDOR_ROOT/core/.rtw_mlme.o.cmd" "$SRC/core/.rtw_mlme.o.cmd"; do
    [ -f "$c" ] && { CMD=$c; break; }
done
[ -n "$CMD" ] || { echo "!! no core/.rtw_mlme.o.cmd - run a full build first" >&2; exit 1; }
# The vendor-path build copies the tree, so its -I flags point at a snapshot.
# Rewrite them back to $SRC so header edits take effect without a full rebuild.
SEDROOT="s#$VENDOR_ROOT#$SRC#g" 
FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' -e 's/^[^ ]*gcc //' \
        -e 's/ -c -o .*$//' -e 's/-Wp,-MD,[^ ]*//' -e 's/-DKBUILD_BASENAME=[^ ]*//' \
        -e 's/-DKBUILD_MODNAME=[^ ]*//' \
        -e "s/-D__TIME__='\"[^\"]*\"'//" -e "s/-D__DATE__='\"[^\"]*\"'//" \
        -e "$SEDROOT")
mkdir -p "$OUT"
eval set -- "$FLAGS" -Wno-builtin-macro-redefined \
    -DKBUILD_BASENAME='\"'"$BASE"'\"' -DKBUILD_MODNAME='\"8188fu\"' \
    -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__="'\"20:43:27\"'"
( cd "$KSRC" && arm-linux-gnueabi-gcc "$@" -c -o "$OUT/$BASE.o" "$SRC/$CFILE" )
exec python3 "$SRC/build/oem/oemdiff.py" --shipped "$SHIPPED" --obj "$OUT/$BASE.o" \
        --also "$FN" --fn "$FN" $EXTRA
