#!/bin/sh
# Assemble one OEM translation unit to /tmp/<unit>.s with the vendor flags.
#   docker exec fuv sh /src/build/oem/asm.sh ez_sc [extra gcc flags...]
set -e
: "${KSRC:=/build/linux-vendor}"
: "${SRC:=/src}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }
B=$1; shift
case "$B" in ez_wifi_config) T=20:43:30 ;; *) T=20:43:27 ;; esac
FLAGS=$(sh "$SRC/build/oem/flags.sh")
eval set -- "$FLAGS" -Wno-builtin-macro-redefined \
    -DKBUILD_BASENAME='\"'"$B"'\"' -DKBUILD_MODNAME='\"8188fu\"' \
    -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__='\"'"$T"'\"' "$@"
cd "$KSRC"
exec arm-linux-gnueabi-gcc "$@" -S -o "/tmp/$B.s" "$SRC/os_dep/linux/$B.c"
