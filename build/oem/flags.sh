#!/bin/sh
# Print the exact compile flags the vendor build uses for a driver object, as
# one line, with $KBUILD_BASENAME / $__TIME__ left to the caller.  Lifted from
# the last real build's core/.rtw_mlme.o.cmd so it tracks the Makefile.
#
#   eval set -- $(sh /src/build/oem/flags.sh)
: "${SRC:=/src}"
VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
for c in "$VENDOR_ROOT/core/.rtw_mlme.o.cmd" "$SRC/core/.rtw_mlme.o.cmd"; do
    [ -f "$c" ] && { CMD=$c; break; }
done
[ -n "$CMD" ] || { echo "!! no core/.rtw_mlme.o.cmd - run a full build first" >&2; exit 1; }
head -1 "$CMD" | sed -e 's/^[^=]*:= *//' \
                     -e 's/^[^ ]*gcc //' \
                     -e 's/ -c -o .*$//' \
                     -e 's/-Wp,-MD,[^ ]*//' \
                     -e "s/-D__TIME__='\"[^\"]*\"'//" \
                     -e "s/-D__DATE__='\"[^\"]*\"'//" \
                     -e 's/-DKBUILD_BASENAME=[^ ]*//' \
                     -e 's/-DKBUILD_MODNAME=[^ ]*//' \
                     -e "s#$VENDOR_ROOT#$SRC#g"
