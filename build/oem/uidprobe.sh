#!/bin/sh
# Compile one driver source file and print its local .NNNN symbol numbers.
set -e
: "${KSRC:=/build/linux-vendor}"; : "${SRC:=/src}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
PATH="$TOOLCHAIN_BIN:$PATH"; export PATH
CFILE=$1; BASE=$(basename "$CFILE" .c)
VENDOR_ROOT=/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217
CMD="$VENDOR_ROOT/core/.rtw_mlme.o.cmd"; [ -f "$CMD" ] || CMD="$SRC/core/.rtw_mlme.o.cmd"
FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' -e 's/^[^ ]*gcc //' -e 's/ -c -o .*$//' \
        -e 's/-Wp,-MD,[^ ]*//' -e 's/-DKBUILD_BASENAME=[^ ]*//' -e 's/-DKBUILD_MODNAME=[^ ]*//' \
        -e "s/-D__TIME__='\"[^\"]*\"'//" -e "s/-D__DATE__='\"[^\"]*\"'//" \
        -e "s#$VENDOR_ROOT#$SRC#g")
mkdir -p /tmp/uid
eval set -- "$FLAGS" -Wno-builtin-macro-redefined -DKBUILD_BASENAME='\"'"$BASE"'\"' \
    -DKBUILD_MODNAME='\"8188fu\"' -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__="'\"20:43:27\"'"
( cd "$KSRC" && arm-linux-gnueabi-gcc "$@" -c -o "/tmp/uid/$BASE.o" "$SRC/$CFILE" 2>/dev/null )
arm-linux-gnueabi-nm "/tmp/uid/$BASE.o" | grep -oE '[A-Za-z_][A-Za-z_0-9]*\.[0-9]+' | sort -u
