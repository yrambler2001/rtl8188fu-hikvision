#!/bin/sh
# Fast iteration loop for the two reconstructed OEM translation units.
#
# Compiles ONLY os_dep/linux/ez_sc.c and os_dep/linux/ez_wifi_config.c -- with
# the driver's own compile flags, lifted verbatim from the last real build's
# .rtw_mlme.o.cmd so it tracks the Makefile automatically -- and scores every
# OEM function against the shipped module.  ~2 s instead of a 158-file build.
#
#   docker exec fuv sh /src/build/oem/run.sh [--fn NAME] [-v]
#
# Note ez_wifi_config.c prints its own build time and the shipped module says
# 20:43:30, three seconds after rtw_debug.c's 20:43:27, so the two units get
# different __TIME__ values here and in the Makefile.
set -e
: "${KSRC:=/build/linux-vendor}"
: "${SRC:=/src}"
: "${SHIPPED:=/orig/8188fu.ko}"
: "${OUT:=/tmp/oem}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }

# Compile flags come from the last real build's .rtw_mlme.o.cmd, so they track
# the Makefile automatically.  Prefer the vendor-path build (build-vendorpath.sh)
# over a plain /src build, because only that one carries -DCONFIG_EZ_WIFI.
VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
for c in "$VENDOR_ROOT/core/.rtw_mlme.o.cmd" "$SRC/core/.rtw_mlme.o.cmd"; do
    [ -f "$c" ] && { CMD=$c; break; }
done
[ -n "$CMD" ] || { echo "!! no core/.rtw_mlme.o.cmd - run a full build first" >&2; exit 1; }

FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' \
                             -e 's/^[^ ]*gcc //' \
                             -e 's/ -c -o .*$//' \
                             -e 's/-Wp,-MD,[^ ]*//' \
                             -e "s/-D__TIME__='\"[^\"]*\"'//" \
                             -e "s/-D__DATE__='\"[^\"]*\"'//" \
                             -e 's/-DKBUILD_BASENAME=[^ ]*//' \
                             -e 's/-DKBUILD_MODNAME=[^ ]*//')

mkdir -p "$OUT"
build() {           # build <basename> <__TIME__>
    B=$1
    eval set -- "$FLAGS" -Wno-builtin-macro-redefined \
        -DKBUILD_BASENAME='\"'"$1"'\"' -DKBUILD_MODNAME='\"8188fu\"' \
        -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__='\"'"$2"'\"'
    ( cd "$KSRC" && arm-linux-gnueabi-gcc "$@" -c -o "$OUT/$B.o" "$SRC/os_dep/linux/$B.c" )
}

build ez_sc          20:43:27
build ez_wifi_config 20:43:30

exec python3 "$SRC/build/oem/oemdiff.py" --shipped "$SHIPPED" \
        --obj "$OUT/ez_sc.o" --obj "$OUT/ez_wifi_config.o" "$@"
