#!/bin/sh
# End-to-end verification: build 8188fu.ko from a clean checkout of HEAD and
# score it against the shipped module.
#
#   sh build/verify.sh [/path/to/shipped/8188fu.ko]
#
# Assumes the `fuv` container is up and prepare-vendor-kernel.sh and
# build-gcc-vendor.sh have already run - see README section 5.
set -e
SHIPPED=${1:-/path/to/8188fu.ko}
CONTAINER=${CONTAINER:-fuv}

echo "== exporting HEAD to ./cleanchk"
rm -rf cleanchk
git archive HEAD --prefix=cleanchk/ | tar -x

echo "== building"
docker exec -e SRC=/src/cleanchk "$CONTAINER" sh /src/build/build-vendorpath.sh >/dev/null

echo "== determinism: rebuilding"
cp cleanchk/8188fu.ko /tmp/verify-first.ko
docker exec -e SRC=/src/cleanchk "$CONTAINER" sh /src/build/build-vendorpath.sh >/dev/null
cmp /tmp/verify-first.ko cleanchk/8188fu.ko && echo "   build is deterministic"

echo "== scoreboard"
python3 build/fulldiff.py "$SHIPPED" cleanchk/8188fu.ko --brief | tail -8

echo "== hashes"
shasum -a 256 "$SHIPPED" cleanchk/8188fu.ko 2>/dev/null || sha256sum "$SHIPPED" cleanchk/8188fu.ko

echo "== cmp"
cmp "$SHIPPED" cleanchk/8188fu.ko && echo "   IDENTICAL" || echo "   (see the scoreboard above)"
