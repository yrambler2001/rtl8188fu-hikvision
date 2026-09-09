#!/bin/sh
# Where the two toolchains live, and the PATH that makes them usable.
#
# This file is *sourced*, not run:
#
#     _here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
#     . "${TOOLCHAIN_ENV:-$_here/toolchain-env.sh}"
#
# WHY IT EXISTS.  There are two arm-linux-gnueabi GCC 6.5.0 installations in
# this project and they are not interchangeable:
#
#   $CROSSTOOL_BIN   kernel.org's crosstool prebuilt, installed by
#                    build/setup-toolchain.sh.  Stock GCC, plus the binutils
#                    2.32 that everything here assembles and links with (see
#                    FINDINGS-toolchain.md for why binutils is not rebuilt).
#                    This is the compiler that configures the vendor kernel:
#                    modules_prepare only needs one for asm-offsets and the
#                    version checks, and nothing it produces depends on which
#                    of the two is used - but it has to be pinned to one of
#                    them, or CI and the local container would differ.
#
#   $VENDOR_GCC_BIN  GCC 6.5.0 rebuilt from the FSF release by
#                    build/build-gcc-vendor.sh with the vendor's
#                    --with-pkgversion.  The *module* must be built with this
#                    one and only this one: the pkgversion string is what GCC
#                    stamps into .comment, 159 times, so building with the
#                    stock compiler changes the SHA-256.
#
# Until this file existed, the only thing that put a cross compiler on PATH was
# an ENV line in build/Dockerfile, which meant the scripts worked inside that
# image and nowhere else.  Every GitHub Actions `run:` step is a fresh shell,
# so a PATH exported by one step is gone by the next, and
# build/prepare-vendor-kernel.sh died with
#
#     ./scripts/gcc-version.sh: arm-linux-gnueabi-gcc: command not found
#
# in the step immediately after the one that had installed that compiler.  The
# fix is not to export PATH harder from the workflow: it is for each script to
# establish its own toolchain, so that it runs correctly in any fresh shell,
# in CI and in the container alike.  One recipe, not two.
#
# Everything below is overridable from the environment and nothing is
# discovered by searching, so an unset or wrong toolchain is an error rather
# than a silent fallback to whatever else happens to be on PATH.

case "$0" in
    *toolchain-env.sh)
        echo "!! build/toolchain-env.sh is sourced, not executed" >&2
        exit 1 ;;
esac

TOOLCHAIN_TARGET=${TOOLCHAIN_TARGET:-arm-linux-gnueabi}
TOOLCHAIN_ROOT=${TOOLCHAIN_ROOT:-/opt}

# The two prefixes.  build/setup-toolchain.sh unpacks the kernel.org tarball
# into $TOOLCHAIN_ROOT, which is why the crosstool path has the shape it has;
# build/build-gcc-vendor.sh is free to install anywhere and installs alongside.
CROSSTOOL_DIR=${CROSSTOOL_DIR:-$TOOLCHAIN_ROOT/gcc-${CROSSTOOL_VER:-6.5.0}-nolibc/$TOOLCHAIN_TARGET}
VENDOR_GCC_DIR=${VENDOR_GCC_DIR:-$TOOLCHAIN_ROOT/gcc-${GCC_VER:-6.5.0}-vendor/$TOOLCHAIN_TARGET}
CROSSTOOL_BIN=$CROSSTOOL_DIR/bin
VENDOR_GCC_BIN=$VENDOR_GCC_DIR/bin

export TOOLCHAIN_TARGET TOOLCHAIN_ROOT
export CROSSTOOL_DIR VENDOR_GCC_DIR CROSSTOOL_BIN VENDOR_GCC_BIN

# Put $1 at the front of PATH, if it holds a target compiler.  Idempotent: a
# directory that is already first is left alone, so sourcing this file twice
# does not grow PATH.  Returns non-zero when there is no compiler there, which
# is not fatal by itself - build/setup-toolchain.sh sources this file before it
# has installed anything.
toolchain_path_prepend() {
    [ -x "$1/$TOOLCHAIN_TARGET-gcc" ] || return 1
    case "$PATH" in
        "$1"|"$1":*) ;;
        *) PATH="$1:$PATH" ;;
    esac
    export PATH
    return 0
}

# The same, but a missing compiler is fatal and the message says how to get it.
# Used wherever falling through to another compiler would produce a module that
# looks right and hashes wrong.
#   $1 directory   $2 what it is   $3 the command that creates it
toolchain_require() {
    if toolchain_path_prepend "$1"; then
        return 0
    fi
    echo "!! no $TOOLCHAIN_TARGET-gcc in $1" >&2
    echo "!! ($2)" >&2
    echo "!! run: $3" >&2
    exit 1
}

# The default PATH for any build step: the crosstool prebuilt, matching the ENV
# line in build/Dockerfile.  The scripts that build the *module* put
# $VENDOR_GCC_BIN in front of this themselves, via $TOOLCHAIN_BIN; nothing else
# may, or the kernel and the module would be prepared by different compilers in
# CI than in the container.
toolchain_path_prepend "$CROSSTOOL_BIN" || :
