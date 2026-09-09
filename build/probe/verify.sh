#!/bin/sh
cd /build/linux
probe() {
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" olddefconfig >/dev/null 2>&1
  make ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- HOSTCFLAGS="$HOSTCFLAGS" modules_prepare >/dev/null 2>&1
  rm -f /probe/probe.ko /probe/probe.o
  make -C /build/linux M=/probe ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- modules >/dev/null 2>&1 || { echo FAILED; return; }
  g(){ arm-linux-gnueabi-readelf -sW /probe/probe.ko | awk -v n="probe_$1" '$4=="OBJECT" && $8==n{print $3}'; }
  echo "    module=$(g module)  net_device=$(g net_device)  device=$(g device)  dev_pm_info=$(g dev_pm_info)  kobject=$(g kobject)"
  echo "    KALLSYMS=$(grep -c '^CONFIG_KALLSYMS=y' .config) PM=$(grep -c '^CONFIG_PM=y' .config) TRACING=$(grep -c '^CONFIG_TRACING=y' .config)"
}
cp .config .config.pristine
echo "[1] pristine image config:"; probe
echo
cp .config.pristine .config
for k in SUSPEND HIBERNATION PM_SLEEP PM KALLSYMS JUMP_LABEL UNUSED_SYMBOLS CONSTRUCTORS FTRACE PERF_EVENTS TRACING DEBUG_SET_MODULE_RONX MODULES_TREE_LOOKUP; do
  ./scripts/config --file .config --disable "$k" 2>/dev/null
done
echo "[2] with PM+MOD disabled:"; probe
echo
echo "  TARGET from shipped .ko:  module=384   net_device aligned to 32 = 992"
