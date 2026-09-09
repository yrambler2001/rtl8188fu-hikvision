#!/bin/sh
# End-to-end verification: build 8188fu.ko from a clean `git archive` of HEAD
# and prove the result is the shipped module, bit for bit.
#
#   sh build/verify.sh [/path/to/shipped/8188fu.ko]
#
# The proof is the SHA-256.  The shipped module is not redistributed with this
# repository, so the hash is the primary assertion and comparing against a copy
# you already have is an optional extra.
#
# Environment:
#   SHIPPED        path to the shipped 8188fu.ko.  Optional; may also be given
#                  as $1.  When set, the scoreboard and a positional `cmp` are
#                  run as well.
#   EXPECT_SHA256  the hash the rebuild must have.  Non-empty by default; set
#                  it empty to skip the assertion.
#   EXEC           how to run the build.  "docker" (default) runs it with
#                  `docker exec` in $CONTAINER; "direct" runs it in the current
#                  environment, which is what CI does - see
#                  .github/workflows/reproduce.yml.
#   CONTAINER      container name for EXEC=docker.  Default fuv.
#   SRC_MOUNT      where this repository is mounted inside that container.
#                  Default /src.
#   OUT            directory the clean export is built in.  Default cleanchk.
#
# For EXEC=docker, prepare-vendor-kernel.sh and build-gcc-vendor.sh must
# already have run in the container - see README section 5.
set -e

EXPECT_SHA256=${EXPECT_SHA256-a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13}
SHIPPED=${1:-${SHIPPED:-}}
EXEC=${EXEC:-docker}
CONTAINER=${CONTAINER:-fuv}
SRC_MOUNT=${SRC_MOUNT:-/src}
OUT=${OUT:-cleanchk}
LOG=${LOG:-.verify-build.log}
FIRST=${FIRST:-.verify-first.ko}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
    else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

# Build the exported tree.  Both modes run the same script; only the way it is
# reached differs, so there is one recipe and not two.
dobuild() {
    if [ "$EXEC" = direct ]; then
        SRC="$PWD/$OUT" sh build/build-vendorpath.sh
    else
        docker exec -e SRC="$SRC_MOUNT/$OUT" "$CONTAINER" \
                sh "$SRC_MOUNT/build/build-vendorpath.sh"
    fi
}

run() {
    if ! dobuild >"$LOG" 2>&1; then
        echo "!! build failed; last 40 lines of $LOG:" >&2
        tail -40 "$LOG" >&2
        exit 1
    fi
}

echo "== exporting HEAD to ./$OUT"
rm -rf "$OUT"
git archive HEAD --prefix="$OUT/" | tar -x

echo "== building"
run

echo "== determinism: rebuilding"
cp "$OUT/8188fu.ko" "$FIRST"
run
cmp "$FIRST" "$OUT/8188fu.ko" && echo "   build is deterministic"
rm -f "$FIRST"

GOT=$(sha256 "$OUT/8188fu.ko")
echo "== sha256"
echo "   rebuilt  $GOT"
if [ -n "$EXPECT_SHA256" ]; then
    echo "   expected $EXPECT_SHA256"
    if [ "$GOT" != "$EXPECT_SHA256" ]; then
        echo "!! HASH MISMATCH - the rebuild is not the shipped module" >&2
        exit 1
    fi
    echo "   MATCH"
fi

if [ -n "$SHIPPED" ] && [ -f "$SHIPPED" ]; then
    echo "== scoreboard"
    python3 build/fulldiff.py "$SHIPPED" "$OUT/8188fu.ko" --brief | tail -8
    echo "== shipped sha256"
    echo "   $(sha256 "$SHIPPED")  $SHIPPED"
    echo "== cmp"
    cmp "$SHIPPED" "$OUT/8188fu.ko" && echo "   IDENTICAL" || echo "   (see the scoreboard above)"
elif [ -n "$SHIPPED" ]; then
    echo "!! \$SHIPPED is set to '$SHIPPED', which does not exist" >&2
    exit 1
else
    echo "== no \$SHIPPED given; the hash above is the whole proof"
fi

rm -rf "$OUT"
