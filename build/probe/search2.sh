#!/bin/sh
cd /build/linux
try() {
  label="$1"; shift
  cp .config.base .config
  for k in "$@"; do ./scripts/config --file .config --disable "$k" 2>/dev/null; done
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" olddefconfig >/dev/null 2>&1
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" modules_prepare >/dev/null 2>&1
  make -C /build/linux M=/probe ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- modules >/dev/null 2>&1 || { echo "  $label: FAILED"; return; }
  g(){ arm-linux-gnueabi-readelf -sW /probe/probe.ko | awk -v n="probe_$1" '$4=="OBJECT" && $8==n{print $3}'; }
  m=$(g module); n=$(g net_device); d=$(g device); na=$(( (n+31)/32*32 ))
  printf "  %-40s module=%-4s net_dev=%-5s(al %-5s) device=%s\n" "$label" "$m" "$n" "$na" "$d"
}
cp .config .config.base
PM="SUSPEND HIBERNATION PM_SLEEP PM"
MOD="KALLSYMS JUMP_LABEL UNUSED_SYMBOLS CONSTRUCTORS FTRACE PERF_EVENTS TRACING DEBUG_SET_MODULE_RONX MODULES_TREE_LOOKUP"
DEV="PINCTRL DMA_CMA NUMA GENERIC_MSI_IRQ_DOMAIN"
NET="MPLS MPLS_ROUTING DCB FCOE NET_L3_MASTER_DEV NET_SWITCHDEV IEEE802154 6LOWPAN BQL NET_DEVLINK WIRELESS_EXT_SPY"
echo "TARGET:                                  module=384  net_dev aligned=992"
try "baseline"
try "+PM"                 $PM
try "+PM +MOD"            $PM $MOD
try "+PM +MOD +DEV"       $PM $MOD $DEV
try "+PM +MOD +DEV +NET"  $PM $MOD $DEV $NET
try "+PM +MOD +NET"       $PM $MOD $NET
