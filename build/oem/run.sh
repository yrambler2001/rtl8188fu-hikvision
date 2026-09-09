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

CMD=$SRC/core/.rtw_mlme.o.cmd
[ -f "$CMD" ] || { echo "!! no $CMD - run a full build first" >&2; exit 1; }

FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' \
                             -e 's/^[^ ]*gcc //' \
                             -e 's/ -c -o .*$//' \
                             -e 's/-Wp,-MD,[^ ]*//' \
                             -e "s/-D__TIME__='\"[^\"]*\"'//" \
                             -e 's/-DKBUILD_BASENAME=[^ ]*//' \
                             -e 's/-DKBUILD_MODNAME=[^ ]*//')

mkdir -p "$OUT"
build() {           # build <basename> <__TIME__>
    eval set -- "$FLAGS" \
        -DKBUILD_BASENAME='\"'"$1"'\"' -DKBUILD_MODNAME='\"8188fu\"' \
        -D__TIME__='\"'"$2"'\"'
    ( cd "$KSRC" && arm-linux-gnueabi-gcc "$@" -c -o "$OUT/$1.o" "$SRC/os_dep/linux/$1.c" )
}

build ez_sc          20:43:27
build ez_wifi_config 20:43:30

exec python3 "$SRC/build/oem/oemdiff.py" --shipped "$SHIPPED" \
        --obj "$OUT/ez_sc.o" --obj "$OUT/ez_wifi_config.o" "$@"
