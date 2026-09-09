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

# bullseye is EOL: its Release files are past Valid-Until. Accept them.
RUN printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid \
 && apt-get -o Acquire::Check-Valid-Until=false update \
 && apt-get install -y --no-install-recommends \
        build-essential bc bison flex libssl-dev libelf-dev kmod \
        xz-utils curl ca-certificates make patch file \
        gcc-arm-linux-gnueabi binutils-arm-linux-gnueabi \
    && rm -rf /var/lib/apt/lists/*

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
 && grep -A2 '^config WIRELESS_EXT' net/wireless/Kconfig

RUN cd /build/linux \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" multi_v7_defconfig \
 && ./scripts/kconfig/merge_config.sh -m .config /build/kernel.fragment \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" olddefconfig \
 && make ARCH=arm CROSS_COMPILE=$CROSS_COMPILE HOSTCFLAGS="$HOSTCFLAGS" -j"$(nproc)" modules_prepare \
 && grep -E 'CONFIG_(SMP|PREEMPT|CPU_V7|THUMB2_KERNEL|ARM_PATCH_PHYS_VIRT|MODULE_UNLOAD|CC_OPTIMIZE_FOR_SIZE)=' .config

WORKDIR /src
