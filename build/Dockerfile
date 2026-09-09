# Build environment reconstructing (as closely as publicly possible) the toolchain
# that produced the shipped 8188fu.ko.
#
# Recovered from the binary:
#   vermagic  = 4.9.129 mod_unload ARMv7 p2v8
#   .comment  = GCC: (arm_multilib_uclibc_20200924) 6.5.0   <-- vendor-built, NOT public
#   ARM attrs = CPU v7-A, FP VFPv2, no Tag_ABI_VFP_args  -> soft-float ABI
#               Tag_ABI_optimization_goals: Aggressive Size -> built with -Os
#
# Closest public stand-in: Debian's soft-float armel cross GCC.
FROM debian:bullseye

ARG KVER=4.9.129

# Prerequisites, and the exact compiler family: the shipped module was built
# with GCC 6.5.0. kernel.org's crosstool prebuilts provide GCC 6.5.0 /
# arm-linux-gnueabi (soft-float, matching the original's missing
# Tag_ABI_VFP_args); "nolibc" is correct, kernel modules are freestanding.
#
# This is one script rather than inline RUN steps because CI runs the identical
# script on the runner (.github/workflows/reproduce.yml), so the image and the
# CI environment cannot drift. It picks the arm64- or the x86_64-hosted
# prebuilt from `uname -m`, which is why this image builds on either host.
#
# toolchain-env.sh travels with it: setup-toolchain.sh sources its sibling for
# the install prefix and the PATH rule, so that this image, the CI runner and a
# bare shell all agree about where the two compilers live.
COPY setup-toolchain.sh toolchain-env.sh /tmp/
RUN sh /tmp/setup-toolchain.sh && rm -f /tmp/setup-toolchain.sh /tmp/toolchain-env.sh
#
# That prebuilt is stock GCC, so its .comment reads "GCC: (GNU) 6.5.0" while the
# shipped module reads "GCC: (arm_multilib_uclibc_20200924) 6.5.0" - GCC's
# --with-pkgversion string, 159 copies of it. build/build-gcc-vendor.sh rebuilds
# GCC 6.5.0 from source with the same configure options plus that pkgversion and
# installs it alongside at /opt/gcc-6.5.0-vendor; the build scripts prefer it when
# present. It is a runtime step (13 minutes, 3 GB of scratch), not an image layer.
# See FINDINGS-toolchain.md.
#
# Redundant since build/toolchain-env.sh puts this on PATH for every script that
# needs it, and kept anyway: it is what makes `docker exec fuv
# arm-linux-gnueabi-gcc ...` and the build/oem/ helpers work interactively.
ENV PATH="/opt/gcc-6.5.0-nolibc/arm-linux-gnueabi/bin:${PATH}"
RUN arm-linux-gnueabi-gcc --version && arm-linux-gnueabi-gcc -v 2>&1 | tail -3

WORKDIR /build
RUN curl -fsSL "https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-${KVER}.tar.xz" \
      | tar -xJ && ln -s "linux-${KVER}" linux

COPY kernel.fragment /build/kernel.fragment

# GCC 10+ defaults to -fno-common, which breaks kernel 4.9 host tools (scripts/dtc).
ENV HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon"
ENV ARCH=arm
ENV CROSS_COMPILE=arm-linux-gnueabi-
ENV KSRC=/build/linux

# CONFIG_WIRELESS_EXT is a hidden symbol in 4.9 that nothing here selects, but the
# shipped module contains the rtw_wx_* WEXT handlers, so the vendor kernel had it.
RUN cd /build/linux \
 && perl -0pi -e 's/^config WIRELESS_EXT\n\tbool\n/config WIRELESS_EXT\n\tbool\n\tdefault y\n/m' net/wireless/Kconfig \
 && perl -0pi -e 's/^config WEXT_PRIV\n\tbool\n/config WEXT_PRIV\n\tbool\n\tdefault y\n/m' net/wireless/Kconfig \
 && grep -A2 -E '^config (WIRELESS_EXT|WEXT_PRIV)' net/wireless/Kconfig

RUN cd /build/linux \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" multi_v7_defconfig \
 && ./scripts/kconfig/merge_config.sh -m .config /build/kernel.fragment \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" olddefconfig \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" -j"$(nproc)" modules_prepare \
 && grep -E 'CONFIG_(SMP|PREEMPT|CPU_V7|THUMB2_KERNEL|ARM_PATCH_PHYS_VIRT|MODULE_UNLOAD|CC_OPTIMIZE_FOR_SIZE)=' .config

WORKDIR /src
