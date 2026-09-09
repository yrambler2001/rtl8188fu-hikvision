#!/bin/sh
# Build GCC 6.5.0 for arm-linux-gnueabi with the *vendor's* --with-pkgversion.
#
# Why: the shipped 8188fu.ko carries, once per translation unit,
#
#     GCC: (arm_multilib_uclibc_20200924) 6.5.0
#
# GCC writes that .ident as  "GCC: (" <pkgversion> ") " <version>, where
# <pkgversion> is whatever ./configure was given in --with-pkgversion (default
# "GNU").  It is a pure string: it reaches .comment and nothing else.  A stock
# GCC 6.5.0 therefore emits "GCC: (GNU) 6.5.0" and 159 copies of a 43-byte
# string in the shipped module face 157 copies of an 18-byte one in ours -
# 9,347 bytes, 25% of the whole remaining byte gap.
#
# What this script does: rebuild GCC 6.5.0 from the FSF release tarball with
# the same configure options as the kernel.org crosstool prebuilt we have been
# using (build/Dockerfile installs arm64-gcc-6.5.0-nolibc-arm-linux-gnueabi),
# changing *only* --with-pkgversion and --prefix.  The stock compiler stays
# installed at /opt/gcc-6.5.0-nolibc so the two can be compared.
#
# The stock prebuilt reports:
#
#   Configured with: /home/arnd/git/gcc/configure --host=aarch64-linux-gnu \
#     --target=arm-linux-gnueabi --enable-targets=all \
#     --prefix=/home/arnd/cross/x86_64/gcc-6.5.0-nolibc/aarch64-linux-gnu/arm-linux-gnueabi \
#     --enable-languages=c --without-headers --disable-bootstrap --disable-nls \
#     --disable-threads --disable-shared --disable-libmudflap --disable-libssp \
#     --disable-libgomp --disable-decimal-float --disable-libquadmath \
#     --disable-libatomic --disable-libcc1 --disable-libmpx \
#     --enable-checking=release
#
# (Arnd builds a Canadian cross: build=x86_64, host=aarch64.  This script does
# a plain native build of the same cross compiler on whatever host it is run
# on - arm64 locally, x86_64 in CI.  See FINDINGS-toolchain.md for why that
# cannot change target code generation, and the CI workflow for the assertion
# that checks it rather than trusting it.)
#
# BINUTILS IS NOT REBUILT.  1,293 same-size functions already assemble
# instruction-identically with the stock binutils 2.32 that ships in the same
# prebuilt, so the assembler is right and touching it could only make things
# worse.  The new prefix is seeded with a copy of it, both so that GCC's
# configure runs its gcc_cv_as_* feature tests against exactly the assembler
# the stock build was configured against, and so the new prefix is a drop-in
# replacement on PATH.
#
# usage:  docker exec fuv sh /src/build/build-gcc-vendor.sh
# result: /opt/gcc-6.5.0-vendor/arm-linux-gnueabi/bin/arm-linux-gnueabi-gcc
set -e

TARGET=arm-linux-gnueabi
GCC_VER=${GCC_VER:-6.5.0}
PKGVERSION=${PKGVERSION:-arm_multilib_uclibc_20200924}
STOCK=${STOCK:-/opt/gcc-6.5.0-nolibc/$TARGET}
PREFIX=${PREFIX:-/opt/gcc-6.5.0-vendor/$TARGET}
WORK=${WORK:-/build/gcc-vendor}
JOBS=${JOBS:-$(nproc)}
INFRA=https://gcc.gnu.org/pub/gcc/infrastructure

# Host triple and host compiler.  build == host, so this is a plain native
# build of a cross compiler and only --target reaches code generation; these
# strings land in the "Configured with:" banner and nowhere else.  They are
# pinned per architecture rather than taken from config.guess so that the
# aarch64 values are exactly the ones this project has always used, and so that
# an unrecognised host is an error rather than a silent change.
#
# CI runs this on x86_64 while local development is arm64.  That the two
# produce the same ARM object code is not assumed here: it is asserted, by the
# SHA-256 check in .github/workflows/reproduce.yml.
case "$(uname -m)" in
    aarch64|arm64) NATIVE_TRIPLE=aarch64-unknown-linux-gnu; NATIVE_PFX=aarch64-linux-gnu ;;
    x86_64|amd64)  NATIVE_TRIPLE=x86_64-pc-linux-gnu;       NATIVE_PFX=x86_64-linux-gnu  ;;
    *) echo "!! unrecognised host $(uname -m); set HOST_TRIPLE, HOST_CC and HOST_CXX" >&2
       exit 1 ;;
esac
HOST_TRIPLE=${HOST_TRIPLE:-$NATIVE_TRIPLE}
HOST_CC=${HOST_CC:-$NATIVE_PFX-gcc}
HOST_CXX=${HOST_CXX:-$NATIVE_PFX-g++}
command -v "$HOST_CC"  >/dev/null 2>&1 || HOST_CC=gcc
command -v "$HOST_CXX" >/dev/null 2>&1 || HOST_CXX=g++

[ -x "$STOCK/bin/$TARGET-as" ] || { echo "!! no stock binutils at $STOCK" >&2; exit 1; }

echo "=== target      $TARGET"
echo "=== pkgversion  $PKGVERSION"
echo "=== prefix      $PREFIX"
echo "=== host        $HOST_TRIPLE  ($HOST_CC / $HOST_CXX)"
echo "=== binutils    $($STOCK/bin/$TARGET-as --version | head -1)"

mkdir -p "$WORK"
cd "$WORK"

# ---------------------------------------------------------------- sources ---
if [ ! -f "gcc-$GCC_VER.tar.xz" ]; then
    echo "== fetching gcc-$GCC_VER.tar.xz"
    curl -fL --retry 3 -o "gcc-$GCC_VER.tar.xz.part" \
         "https://ftp.gnu.org/gnu/gcc/gcc-$GCC_VER/gcc-$GCC_VER.tar.xz"
    mv "gcc-$GCC_VER.tar.xz.part" "gcc-$GCC_VER.tar.xz"
fi
echo "== gcc-$GCC_VER.tar.xz sha256: $(sha256sum "gcc-$GCC_VER.tar.xz" | cut -d' ' -f1)"

if [ ! -d "gcc-$GCC_VER" ]; then
    echo "== unpacking"
    tar xf "gcc-$GCC_VER.tar.xz"
fi

# GMP / MPFR / MPC / ISL, built in-tree.
#
# We do NOT run contrib/download_prerequisites: the copy in the 6.5.0 tarball
# is the 2010 one.  It fetches over ftp://gcc.gnu.org (dead) and it names the
# *minimum* supported versions - gmp-4.3.2, mpfr-2.4.2, mpc-0.8.1, isl-0.15 -
# and gmp 4.3.2 (2009) predates aarch64, so its configure cannot even
# recognise this host.  These are the versions GCC's own infrastructure
# directory shipped for the 6.4/6.5 era and that GCC 7's rewritten
# download_prerequisites names.
#
# None of the four can reach ARM code generation: GMP/MPFR/MPC only implement
# the compiler's own exact arithmetic (correctly-rounded, so version
# independent), and ISL is only consulted for -floop-* / Graphite, which -Os
# never enables.
PREREQS=${PREREQS:-"gmp-6.1.0.tar.bz2 mpfr-3.1.4.tar.bz2 mpc-1.0.3.tar.gz isl-0.16.1.tar.bz2"}
cd "gcc-$GCC_VER"
echo "== prerequisites: $PREREQS"
for tarball in $PREREQS; do
    dir=$(echo "$tarball" | sed 's/\.tar\..*//')
    lib=$(echo "$dir" | sed 's/-[0-9].*//')
    # Key the "already there" test on the *versioned* directory, and re-point the
    # symlink unconditionally with -n: a leftover gmp -> gmp-4.3.2 from an earlier
    # run would otherwise silently win, and `ln -sf x gmp` on an existing symlink
    # to a directory creates gmp/x rather than replacing it.
    if [ ! -d "$dir" ]; then
        [ -f "../$tarball" ] || curl -fL --retry 3 -o "../$tarball" "$INFRA/$tarball"
        tar xf "../$tarball"
    fi
    ln -sfn "$dir" "$lib"
done
echo "== in-tree: $(ls -ld gmp mpfr mpc isl | sed 's/.* -> //' | tr '\n' ' ')"
cd "$WORK"

# ------------------------------------------------------- seed the binutils ---
# GCC's configure looks for the target assembler at $prefix/$target/bin/as
# before it falls back to $PATH; that is where Arnd's build found it too,
# because he installs binutils into the same prefix first.
mkdir -p "$PREFIX/bin" "$PREFIX/$TARGET/bin"
cp -a "$STOCK/$TARGET/bin/." "$PREFIX/$TARGET/bin/"
for t in addr2line ar as c++filt elfedit gprof ld ld.bfd nm objcopy objdump \
         ranlib readelf size strings strip; do
    [ -f "$STOCK/bin/$TARGET-$t" ] && cp -a "$STOCK/bin/$TARGET-$t" "$PREFIX/bin/"
done

# ------------------------------------------------------------- configure ----
# --build and --host are the canonical four-field triple for this host, rather
# than Arnd's three-field --host=aarch64-linux-gnu, which describes his Canadian
# cross (build=x86_64).  Since build == host this is a plain native build either
# way; the strings only reach the "Configured with:" banner.  (The three-field form also happens to be rejected by GMP's wrapped
# config.sub in old GMP releases - 4.3.2 says "machine `aarch64' not
# recognized" - though gmp-6.1.0, which this script fetches, accepts it.)
mkdir -p build
cd build
if [ ! -f config.status ]; then
    echo "== configure"
    PATH="$PREFIX/bin:$PATH" \
    "../gcc-$GCC_VER/configure" \
        --build="$HOST_TRIPLE" \
        --host="$HOST_TRIPLE" \
        --target=$TARGET \
        --enable-targets=all \
        --prefix="$PREFIX" \
        --enable-languages=c \
        --without-headers \
        --disable-bootstrap \
        --disable-nls \
        --disable-threads \
        --disable-shared \
        --disable-libmudflap \
        --disable-libssp \
        --disable-libgomp \
        --disable-decimal-float \
        --disable-libquadmath \
        --disable-libatomic \
        --disable-libcc1 \
        --disable-libmpx \
        --enable-checking=release \
        --with-pkgversion="$PKGVERSION" \
        CC="$HOST_CC" CXX="$HOST_CXX" \
        CFLAGS="-O2 -fcommon" CXXFLAGS="-O2 -fcommon"
fi

# ----------------------------------------------------------------- build ----
echo "== make -j$JOBS"
PATH="$PREFIX/bin:$PATH" make -j"$JOBS"
echo "== make install"
PATH="$PREFIX/bin:$PATH" make install

# ------------------------------------------------------------------ check ---
echo "=== result ==="
"$PREFIX/bin/$TARGET-gcc" --version | head -1
"$PREFIX/bin/$TARGET-gcc" -v 2>&1 | tail -2
cd /tmp
printf 'int x;\n' > pkgver-probe.c
"$PREFIX/bin/$TARGET-gcc" -c pkgver-probe.c -o pkgver-probe.o
"$PREFIX/bin/$TARGET-readelf" -p .comment pkgver-probe.o
