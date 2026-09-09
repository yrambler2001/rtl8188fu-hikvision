#!/bin/sh
# Compile an arbitrary C file with the OEM translation unit's flags and print
# "<DECL_UID> <kind> <function name>" for every __func__/__FUNCTION__ array,
# in UID order.  Used to probe GCC's DECL_UID accounting.
#   uidat.sh /tmp/probe/ez_sc.c [basename-for-KBUILD_BASENAME] [__TIME__]
set -e
: "${KSRC:=/build/linux-vendor}"; : "${SRC:=/src}"
: "${TOOLCHAIN_BIN:=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin}"
[ -x "$TOOLCHAIN_BIN/arm-linux-gnueabi-gcc" ] && { PATH="$TOOLCHAIN_BIN:$PATH"; export PATH; }
CFILE=$1
B=${2:-$(basename "$CFILE" .c)}
T=${3:-20:43:27}
VENDOR_ROOT=${VENDOR_ROOT:-/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217}
for c in "$VENDOR_ROOT/core/.rtw_mlme.o.cmd" "$SRC/core/.rtw_mlme.o.cmd"; do
    [ -f "$c" ] && { CMD=$c; break; }
done
FLAGS=$(head -1 "$CMD" | sed -e 's/^[^=]*:= *//' -e 's/^[^ ]*gcc //' -e 's/ -c -o .*$//' \
        -e 's/-Wp,-MD,[^ ]*//' -e "s/-D__TIME__='\"[^\"]*\"'//" -e "s/-D__DATE__='\"[^\"]*\"'//" \
        -e 's/-DKBUILD_BASENAME=[^ ]*//' -e 's/-DKBUILD_MODNAME=[^ ]*//' \
        -e "s#$VENDOR_ROOT#$SRC#g")
O=${OBJ:-/tmp/uidat.o}
eval set -- "$FLAGS" -Wno-builtin-macro-redefined -DKBUILD_BASENAME='\"'"$B"'\"' \
    -DKBUILD_MODNAME='\"8188fu\"' -D__DATE__="'\"Dec 25 2023\"'" -D__TIME__='\"'"$T"'\"'
( cd "$KSRC" && arm-linux-gnueabi-gcc "$@" -c -o "$O" "$CFILE" 2>/dev/null )
python3 - "$O" <<'PY'
import sys
sys.path.insert(0,"/src/build/oem")
from elf import ELF
e=ELF(sys.argv[1])
rows=[]
for s in e.syms:
    n=s["name"]
    if not (n.startswith("__func__.") or n.startswith("__FUNCTION__.")): continue
    sec=e.sh[s["shndx"]]
    txt=e.d[sec["off"]+s["value"]:sec["off"]+s["value"]+64].split(b"\0")[0].decode()
    rows.append((int(n.rsplit(".",1)[1]), n.split(".")[0], txt))
rows.sort()
for uid,kind,txt in rows: print(uid, kind, txt)
PY
