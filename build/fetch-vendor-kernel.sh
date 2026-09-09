#!/bin/sh
# Fetch the Fullhan vendor kernel tree.
#
# It is stock Linux 4.9.129 with the Fullhan BSP patch
# 0000-fh8852-kernel-4.9.129.vendor.patch applied and nothing else, and it is
# public: OpenIPC/linux at the commit pinned below, whose commit message is
# that patch's own filename. See FINDINGS-vendor-kernel.md.
#
# ~700 MB unpacked, so this pulls exactly one commit and no history, as a
# tarball. CI uses it; locally it is an alternative to having the tree already
# and bind-mounting it at /vendor-src.
#
#   VENDOR_SRC=/somewhere sh build/fetch-vendor-kernel.sh
set -e

VENDOR_REPO=${VENDOR_REPO:-OpenIPC/linux}
VENDOR_COMMIT=${VENDOR_COMMIT:-6bde37dba95d28db55a9962df97b5887ab1dbeaa}
VENDOR_SRC=${VENDOR_SRC:-/build/linux-openipc}

if [ -d "$VENDOR_SRC/arch/arm/mach-fh" ]; then
    echo "== $VENDOR_SRC already present"
else
    echo "== fetching $VENDOR_REPO @ $VENDOR_COMMIT -> $VENDOR_SRC"
    rm -rf "$VENDOR_SRC" "$VENDOR_SRC.tmp"
    mkdir -p "$VENDOR_SRC.tmp"
    curl -fL --retry 3 \
        "https://codeload.github.com/$VENDOR_REPO/tar.gz/$VENDOR_COMMIT" \
        | tar -C "$VENDOR_SRC.tmp" -xzf -
    top=$(ls "$VENDOR_SRC.tmp")
    mv "$VENDOR_SRC.tmp/$top" "$VENDOR_SRC"
    rmdir "$VENDOR_SRC.tmp"
fi

# None of this is the real check - the real check is the SHA-256 of the module
# the tree produces - but a wrong tree should say so here rather than forty
# minutes later.
cd "$VENDOR_SRC"
[ -d arch/arm/mach-fh ] || {
    echo "!! $VENDOR_SRC has no arch/arm/mach-fh: not the Fullhan BSP" >&2; exit 1; }
[ -f arch/arm/configs/fh8856v200_defconfig ] || {
    echo "!! $VENDOR_SRC has no fh8856v200_defconfig" >&2; exit 1; }
kver="$(sed -n 's/^VERSION *= *//p'    Makefile | head -1)"
kver="$kver.$(sed -n 's/^PATCHLEVEL *= *//p' Makefile | head -1)"
kver="$kver.$(sed -n 's/^SUBLEVEL *= *//p'   Makefile | head -1)"
[ "$kver" = 4.9.129 ] || {
    echo "!! $VENDOR_SRC is Linux $kver, expected 4.9.129" >&2; exit 1; }

echo "== ok: Linux $kver, Fullhan BSP, $(du -sh . | cut -f1) at $VENDOR_SRC"
