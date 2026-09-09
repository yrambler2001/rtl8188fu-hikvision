#!/bin/sh
# Copy the bind-mounted vendor kernel tree into the container and run
# `modules_prepare` on it, so out-of-tree modules can be built against it.
#
# We only need headers + Module.symvers machinery, not a bootable kernel.
set -e

# The toolchain.  modules_prepare compiles arch/arm/kernel/asm-offsets.c and
# runs scripts/gcc-version.sh, so it needs a cross compiler on PATH - and in a
# fresh shell (a GitHub Actions step, say) there is none, which is what used to
# break this script in CI with "arm-linux-gnueabi-gcc: command not found".
# Establish it here rather than relying on the caller.
#
# Which compiler: the stock kernel.org crosstool, deliberately, and not the
# vendor-pkgversion GCC that the *module* is built with.  Nothing modules_prepare
# produces depends on the choice - the two are the same compiler apart from a
# string that only reaches .comment - but it has to be the same choice
# everywhere, and the container has only the crosstool on PATH.  Override with
# KERNEL_TOOLCHAIN_BIN to use another.
_here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "${TOOLCHAIN_ENV:-$_here/toolchain-env.sh}"
KERNEL_TOOLCHAIN_BIN=${KERNEL_TOOLCHAIN_BIN:-$CROSSTOOL_BIN}
toolchain_require "$KERNEL_TOOLCHAIN_BIN" \
    "the kernel is configured with the stock crosstool prebuilt" \
    "sh build/setup-toolchain.sh"

# VENDOR_SRC is the pristine tree; KSRC is where it is configured.  They differ
# by default because kbuild writes .config, autoconf.h, include/generated/* and
# host binaries all over the source directory, and the bind-mounted host tree
# has to stay pristine.  Set KSRC equal to VENDOR_SRC - or VENDOR_COPY=0 - to
# configure in place, which is what CI does: there the tree is a throwaway that
# build/fetch-vendor-kernel.sh has just unpacked.
VENDOR_SRC="${VENDOR_SRC:-/vendor-src}"
KSRC="${KSRC:-/build/linux-vendor}"
VENDOR_COPY="${VENDOR_COPY:-1}"
DEFCONFIG="${VENDOR_DEFCONFIG:-fh8856v200_defconfig}"
: "${HOSTCFLAGS:=-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon}"

if [ "$KSRC" = "$VENDOR_SRC" ]; then VENDOR_COPY=0; fi

# GCC 10+ host tools: 4.9's scripts/ assume -fcommon and gnu89. Keep HOSTCFLAGS
# a single quoted word so `make` sees one argument.
kmake() {
    make ARCH=arm CROSS_COMPILE="$TOOLCHAIN_TARGET-" HOSTCFLAGS="$HOSTCFLAGS" "$@"
}

if [ "$VENDOR_COPY" = 1 ] && [ ! -d "$KSRC" ]; then
    if [ ! -d "$VENDOR_SRC/arch/arm/mach-fh" ]; then
        echo "!! $VENDOR_SRC does not look like the Fullhan tree (no arch/arm/mach-fh)" >&2
        exit 1
    fi
    echo "== copying $VENDOR_SRC -> $KSRC (752 MB, takes a minute)"
    mkdir -p "$KSRC"
    tar -C "$VENDOR_SRC" --exclude=.git -cf - . | tar -C "$KSRC" -xf -
fi

# Whichever tree we are about to configure, it has to be the right one.
if [ ! -d "$KSRC/arch/arm/mach-fh" ]; then
    echo "!! $KSRC does not look like the Fullhan tree (no arch/arm/mach-fh)" >&2
    exit 1
fi

cd "$KSRC"

echo "== cc  $("$TOOLCHAIN_TARGET-gcc" --version | head -1)  [$KERNEL_TOOLCHAIN_BIN]"

# ---------------------------------------------------------------------------
# Retarget the board from ARMv6 to ARMv7.
#
# This BSP drop ships exactly one board choice, ARCH_FH885xV200, and it does
# `select CPU_V6`. All 12 defconfigs therefore compile with -march=armv6 /
# -D__LINUX_ARM_ARCH__=6 and stamp vermagic "ARMv6".
#
# The camera in hand is an FH865x (Cortex-A7), and the shipped 8188fu.ko says
# "4.9.129 mod_unload ARMv7 p2v8". arch/arm/mach-fh/pmu.c references
# CONFIG_ARCH_FH865x, but no Kconfig in this tree defines it - the FH865x board
# entry lives in a sibling Fullhan BSP drop we do not have. Everything else in
# mach-fh (FULLHAN_INTC, FULLHAN_TIMER, the FH_* drivers) is shared.
#
# So flip the one `select`. Consequences, all of them wanted:
#   -march=armv7-a, __LINUX_ARM_ARCH__=7          (matches the shipped codegen)
#   vermagic "ARMv7"                              (matches .modinfo)
#   ARM_L1_CACHE_SHIFT_6 "default y if CPU_V7"    (64-byte ____cacheline_aligned)
# Set VENDOR_CPU_V7=0 to skip and reproduce the stock-BSP ARMv6 numbers.
if [ "${VENDOR_CPU_V7:-1}" = 1 ]; then
    perl -0pi -e 's/(config ARCH_FH885xV200\n\s*bool "Fullhan FH885xV200"\n\s*select )CPU_V6\n/${1}CPU_V7\n/' \
        arch/arm/mach-fh/Kconfig
    grep -A2 '^config ARCH_FH885xV200' arch/arm/mach-fh/Kconfig
fi

echo "== $DEFCONFIG"
kmake "$DEFCONFIG"
echo "== modules_prepare"
kmake -j"$(nproc)" modules_prepare

echo "== sanity"
grep -E '^CONFIG_(WIRELESS_EXT|WEXT_CORE|WEXT_PRIV|WEXT_SPY|CFG80211|SMP|PREEMPT_NONE|CPU_V6|CPU_V7|ARM_L1_CACHE_SHIFT|THUMB2_KERNEL|ARM_PATCH_PHYS_VIRT|MODULE_UNLOAD|CC_OPTIMIZE_FOR_SIZE|KALLSYMS|FH_CHIP_NAME)=' .config || true
echo "-- vermagic:"
cat include/generated/utsrelease.h
