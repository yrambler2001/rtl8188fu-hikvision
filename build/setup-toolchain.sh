#!/bin/sh
# Install the build prerequisites and kernel.org's crosstool GCC 6.5.0
# arm-linux-gnueabi prebuilt at /opt/gcc-6.5.0-nolibc.
#
# One recipe, two callers, so that they cannot drift:
#   * build/Dockerfile bakes it into the local build image;
#   * .github/workflows/reproduce.yml runs it directly on the CI runner.
#
# The prebuilt is selected by the *host* architecture. kernel.org publishes an
# arm64-hosted and an x86_64-hosted build of the same cross compiler; local
# development here is arm64 and GitHub's runners are x86_64. The target is
# arm-linux-gnueabi (soft-float, nolibc) either way, and nolibc is right
# because kernel modules are freestanding.
#
# This is not the compiler that finally matters: build/build-gcc-vendor.sh
# rebuilds GCC 6.5.0 from the FSF release with the vendor's --with-pkgversion,
# and that is what the module is built with. What this prebuilt supplies is
# binutils 2.32 - deliberately *not* rebuilt, see FINDINGS-toolchain.md - and a
# stock compiler to diff the rebuilt one against.
set -e

PREFIX=${PREFIX:-/opt}
CROSSTOOL_VER=${CROSSTOOL_VER:-6.5.0}
SKIP_APT=${SKIP_APT:-0}

# Pin the host packages to a fixed point in Debian's archive.
#
# bullseye is EOL and is being moved to archive.debian.org. While that is in
# flight, deb.debian.org serves a debian-security index whose pool files it
# 404s on, and this step fails at random for reasons that have nothing to do
# with the reproduction. snapshot.debian.org is Debian's own time machine: an
# immutable view of the whole archive at one timestamp, holding every version
# ever published. Pinning it makes the host environment reproducible rather
# than merely working today - the same argument this project makes about the
# compiler and the kernel.
#
# The timestamp below reproduces what the local build image already contains:
# Debian 11, gcc 10.2.1-6, libc6 2.31-13+deb11u14. Set APT_SNAPSHOT= (empty) to
# use whatever sources the base image ships with instead.
APT_SNAPSHOT=${APT_SNAPSHOT-20260801T000000Z}

case "${CT_HOST:-$(uname -m)}" in
    aarch64|arm64) CT_HOST=arm64  ;;
    x86_64|amd64)  CT_HOST=x86_64 ;;
    *) echo "!! no kernel.org crosstool prebuilt for $(uname -m); set CT_HOST" >&2; exit 1 ;;
esac

if [ "$SKIP_APT" != 1 ]; then
    # bullseye is EOL, so its Release files are past Valid-Until: accept them.
    printf 'Acquire::Check-Valid-Until "false";\nAcquire::Retries "5";\n' \
        > /etc/apt/apt.conf.d/99no-check-valid

    codename=$(. /etc/os-release 2>/dev/null; echo "${VERSION_CODENAME:-}")
    if [ -n "$APT_SNAPSHOT" ] && [ -n "$codename" ]; then
        echo "== apt sources: snapshot.debian.org @ $APT_SNAPSHOT ($codename)"
        cat > /etc/apt/sources.list <<SRCLIST
deb http://snapshot.debian.org/archive/debian/$APT_SNAPSHOT $codename main
deb http://snapshot.debian.org/archive/debian/$APT_SNAPSHOT $codename-updates main
deb http://snapshot.debian.org/archive/debian-security/$APT_SNAPSHOT $codename-security main
SRCLIST
        rm -f /etc/apt/sources.list.d/*.list 2>/dev/null || true
    fi

    n=0
    until apt-get -o Acquire::Check-Valid-Until=false update \
       && apt-get install -y --no-install-recommends \
              build-essential bc bison flex libssl-dev libelf-dev kmod \
              xz-utils curl ca-certificates make patch file
    do
        n=$((n + 1))
        [ "$n" -lt 3 ] || { echo "!! apt failed $n times" >&2; exit 1; }
        echo "== apt failed, retry $n/3 in 20s" >&2
        sleep 20
    done
    rm -rf /var/lib/apt/lists/*
fi

CT_DIR="$PREFIX/gcc-$CROSSTOOL_VER-nolibc/arm-linux-gnueabi"
if [ -x "$CT_DIR/bin/arm-linux-gnueabi-gcc" ]; then
    echo "== crosstool already installed at $CT_DIR"
else
    url="https://mirrors.edge.kernel.org/pub/tools/crosstool/files/bin/$CT_HOST/$CROSSTOOL_VER/$CT_HOST-gcc-$CROSSTOOL_VER-nolibc-arm-linux-gnueabi.tar.xz"
    echo "== fetching $url"
    mkdir -p "$PREFIX"
    curl -fsSL --retry 3 "$url" | tar -C "$PREFIX" -xJ
fi

"$CT_DIR/bin/arm-linux-gnueabi-gcc" --version | head -1
"$CT_DIR/bin/arm-linux-gnueabi-as"  --version | head -1
