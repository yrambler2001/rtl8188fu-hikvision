#!/bin/sh
# Compile one OEM translation unit with GCC dump flags; dumps land in /tmp/dumps.
#   docker exec fuv sh /src/build/oem/dump.sh ez_wifi_config -fdump-rtl-ira-all
set -e
: "${KSRC:=/build/linux-vendor}"
: "${SRC:=/src}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }
B=$1; shift
EXTRA="$*"
VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
for c in "$VENDOR_ROOT/core/.rtw_mlme.o.cmd" "$SRC/core/.rtw_mlme.o.cmd"; do
    [ -f "$c" ] && { CMD=$c; break; }
done
SEDROOT="s#$VENDOR_ROOT#$SRC#g"
FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' -e 's/^[^ ]*gcc //' -e 's/ -c -o .*$//' \
        -e 's/-Wp,-MD,[^ ]*//' -e "s/-D__TIME__='\"[^\"]*\"'//" -e "s/-D__DATE__='\"[^\"]*\"'//" \
        -e 's/-DKBUILD_BASENAME=[^ ]*//' -e 's/-DKBUILD_MODNAME=[^ ]*//' -e "$SEDROOT")
rm -rf /tmp/dumps; mkdir -p /tmp/dumps
eval set -- "$FLAGS" -Wno-builtin-macro-redefined \
    -DKBUILD_BASENAME='\"'"$B"'\"' -DKBUILD_MODNAME='\"8188fu\"' \
    -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__="'\"20:43:30\"'" $EXTRA
cd "$KSRC"
# SRCFILE lets the same dump run against a lab variant instead of the tree copy
: "${SRCFILE:=$SRC/os_dep/linux/$B.c}"
exec arm-linux-gnueabi-gcc "$@" -c -o "/tmp/dumps/$B.o" "$SRCFILE" 
