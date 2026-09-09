#!/bin/sh
# Compile build/szprobe/szprobe.c with the driver's own flags and print the
# struct sizes / offsets it encodes.
#
#   sh build/szprobe/run.sh [extra cc flags...]
#
# The flag set is lifted verbatim from the last real build's
# core/.rtw_mlme.o.cmd, so it tracks the Makefile automatically. Extra args are
# appended, which is how you sweep a candidate #ifdef:
#   sh build/szprobe/run.sh -DCONFIG_APPEND_VENDOR_IE_ENABLE
set -e
: "${KSRC:=/build/linux-vendor}"
CMD=/src/core/.rtw_mlme.o.cmd
[ -f "$CMD" ] || { echo "!! no $CMD - run a build first" >&2; exit 1; }

# Everything between "arm-linux-gnueabi-gcc" and "-c -o ..." on the first line.
FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' \
                             -e 's/^[^ ]*gcc //' \
                             -e 's/ -c -o .*$//' \
                             -e 's/-Wp,-MD,[^ ]*//')
cd "$KSRC"
eval set -- "$FLAGS" -DKBUILD_BASENAME='\"szprobe\"' -DKBUILD_MODNAME='\"8188fu\"' "$@"
arm-linux-gnueabi-gcc "$@" -c -o /tmp/szprobe.o /src/build/szprobe/szprobe.c
arm-linux-gnueabi-readelf -sW /tmp/szprobe.o \
  | awk '$8 ~ /^szp_/ {printf "sizeof  %-24s %6d\n", substr($8,5), $3}
         $8 ~ /^szo_/ {printf "offset  %-24s %6d\n", substr($8,5), $3-1}'
