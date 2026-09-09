#!/bin/sh
# Fast oracle: tweak kernel config, re-prepare, report struct sizes.
# targets recovered from the shipped .ko:  module=384   ALIGN(net_device,32)=992
cd /build/linux
try() {
  label="$1"; shift
  cp .config.base .config
  for kv in "$@"; do
    key=$(echo "$kv" | cut -d= -f1); val=$(echo "$kv" | cut -d= -f2)
    ./scripts/config --file .config --set-val "$key" "$val" 2>/dev/null || true
    [ "$val" = "n" ] && ./scripts/config --file .config --disable "$key" 2>/dev/null || true
  done
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" olddefconfig >/dev/null 2>&1
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" modules_prepare >/dev/null 2>&1
  make -C /build/linux M=/probe ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- modules >/dev/null 2>&1 || { echo "  $label: BUILD FAILED"; return; }
  m=$(arm-linux-gnueabi-readelf -sW /probe/probe.ko | awk '$4=="OBJECT" && $8=="probe_module"{print $3}')
  n=$(arm-linux-gnueabi-readelf -sW /probe/probe.ko | awk '$4=="OBJECT" && $8=="probe_net_device"{print $3}')
  d=$(arm-linux-gnueabi-readelf -sW /probe/probe.ko | awk '$4=="OBJECT" && $8=="probe_device"{print $3}')
  na=$(( (n + 31) / 32 * 32 ))
  printf "  %-46s module=%-4s net_device=%-5s (aligned %-5s) device=%s\n" "$label" "$m" "$n" "$na" "$d"
}
cp .config .config.base
echo "TARGET                                         module=384  net_device aligned=992"
try "baseline" ""
try "PM_SLEEP=n"                    SUSPEND=n HIBERNATION=n PM_SLEEP=n
try "PM=n"                          SUSPEND=n HIBERNATION=n PM_SLEEP=n PM=n
try "KALLSYMS=n"                    KALLSYMS=n
try "IPV6=n"                        IPV6=n
try "XFRM=n"                        XFRM_USER=n XFRM=n
try "SYSFS=n"                       SYSFS=n
try "PM=n + KALLSYMS=n"             SUSPEND=n HIBERNATION=n PM_SLEEP=n PM=n KALLSYMS=n
try "PM=n KALLSYMS=n IPV6=n XFRM=n" SUSPEND=n HIBERNATION=n PM_SLEEP=n PM=n KALLSYMS=n IPV6=n XFRM_USER=n XFRM=n
