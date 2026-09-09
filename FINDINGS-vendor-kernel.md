# Barrier 3: building against the Fullhan vendor kernel

Barrier 3 was "vendor kernel tree + `.config`". It is now closed far enough that it
is no longer the bottleneck: **semantic identity went from 2197/3939 functions
(55.8%) to 2570/3939 (65.2%)**, and every offset-correction family that could be
blamed on kernel headers has disappeared from the histogram. What is left is one
single driver-side struct discrepancy, described at the end.

## The tree

The tree this work builds against (752 MB) is stock Linux 4.9.129 with the
Fullhan vendor patch (`0000-fh8852-kernel-4.9.129.vendor.patch`) applied and
nothing else — in particular no OpenIPC changes. It carries `arch/arm/mach-fh/`
with six board directories (`fh885{2,6,8}v2{0,1}0`) and twelve matching entries
in `arch/arm/configs/`.

It is publicly fetchable: **`OpenIPC/linux` at commit `6bde37dba95d`**, whose
commit message is that patch's own filename. `build/fetch-vendor-kernel.sh`
shallow-fetches exactly that commit, which is what CI does; a tree obtained any
other way is checked by the same thing everything else is, the SHA-256 of the
module it produces.

Those twelve "defconfigs" are not minimal defconfigs; they are full 2253-line
`.config` dumps. They differ only in `CONFIG_FH_CHIP_NAME` and `CONFIG_MACH_*`,
so the module ABI they produce is identical and any one of them serves. This work
used **`fh8856v200_defconfig`**.

The tree is not copied into the build image. `build/Dockerfile.vendor` derives from
`rtl8188fu-build:latest` (Debian bullseye + kernel.org crosstool GCC 6.5.0
`arm-linux-gnueabi`, soft-float, nolibc) and expects the tree bind-mounted read-only
at `/vendor-src`; `build/prepare-vendor-kernel.sh` tars it into `/build/linux-vendor`
inside the container before configuring, so the host copy stays pristine.

`modules_prepare` needed **no workarounds**: no missing devicetree, no unbuildable
board file, no stubbed Kconfig. The only concession is the one the stock build
already made — `HOSTCFLAGS="-Wall -O2 -fomit-frame-pointer -std=gnu89 -fcommon"`,
because 4.9's host tools predate GCC 10's `-fno-common` default.

## Wireless extensions: nothing to patch

`build/Dockerfile` had to hand-patch `net/wireless/Kconfig` with two `perl -0pi`
one-liners, because `WIRELESS_EXT` and `WEXT_PRIV` are prompt-less `bool`s that
nothing in `multi_v7_defconfig` selects, yet the shipped module plainly has them
(it exports the `rtw_wx_*` handlers and its `rtw_handlers_def` is 24 bytes, the
size of `struct iw_handler_def` *with* `CONFIG_WEXT_PRIV`).

The vendor tree's `net/wireless/Kconfig` is stock, but the vendor defconfig sets
`CONFIG_HOSTAP=y`, and `drivers/net/wireless/intersil/hostap/Kconfig` does
`select WIRELESS_EXT` and `select WEXT_PRIV`. So both land honestly:

```
CONFIG_WIRELESS_EXT=y   CONFIG_WEXT_CORE=y   CONFIG_WEXT_SPY=y   CONFIG_WEXT_PRIV=y
```

**No Kconfig patching was required.** That is worth saying plainly, because it also
means the vendor really did ship a WEXT-capable kernel rather than us assuming one.

## One change was required: ARMv6 → ARMv7

This BSP drop offers exactly one board choice, and it hardcodes an ARMv6 core:

```
config ARCH_FH885xV200
        bool "Fullhan FH885xV200"
        select CPU_V6
```

All twelve defconfigs therefore compile with `-march=armv6`,
`-D__LINUX_ARM_ARCH__=6`, and stamp `vermagic` as `ARMv6`. The camera in hand is an
**FH865x** (Cortex-A7), and the shipped module says `4.9.129 mod_unload ARMv7 p2v8`.
`arch/arm/mach-fh/pmu.c` references `CONFIG_ARCH_FH865x`, but no Kconfig in this
tree defines it — the FH865x board entry lives in a sibling Fullhan BSP drop that we
do not have. Everything else under `mach-fh` (`FULLHAN_INTC`, `FULLHAN_TIMER`, the
`FH_*` drivers) is shared between the two.

So `build/prepare-vendor-kernel.sh` flips that one `select` to `CPU_V7`
(set `VENDOR_CPU_V7=0` to reproduce the stock-BSP ARMv6 numbers). Three consequences,
all of them the ones we want:

* `-march=armv7-a`, `__LINUX_ARM_ARCH__=7` — matching the shipped codegen;
* `vermagic` becomes `4.9.129 mod_unload ARMv7 p2v8`, an exact match;
* `ARM_L1_CACHE_SHIFT_6` is `default y if CPU_V7`, so `____cacheline_aligned`
  becomes 64-byte — which is exactly what `sizeof(struct module)` needed.

## The struct-size oracle

`build/probe/` compiles one global per kernel struct sized by `sizeof()`, so the
ELF symbol sizes in `probe.ko` read out the struct layout of whatever kernel is
prepared. Against the three targets recovered from the shipped binary:

| measurement | target | stock 4.9.129 + `multi_v7_defconfig` + fragment | vendor BSP as shipped (ARMv6) | **vendor BSP + CPU_V7** |
|---|---:|---:|---:|---:|
| `sizeof(struct module)` (= size of `__this_module`) | **384** | 384 | 352 | **384** |
| `ALIGN(sizeof(struct net_device), 32)` (= `netdev_priv()` offset) | **992** | 1120 | 992 | **992** |
| `sizeof(struct iw_handler_def)` (= size of `rtw_handlers_def`) | **24** | 24 | 24 | **24** |

All three match. The stock build only reached 384 by hand-disabling nine options
(`KALLSYMS`, `JUMP_LABEL`, `FTRACE`, …) in `build/kernel.fragment`; the vendor
config reaches it with `CONFIG_KALLSYMS=y` and `CONFIG_JUMP_LABEL=y` still on,
purely through the 64-byte cache line. The reconstructed fragment was fitting the
right number for the wrong reason — a useful reminder that a single scalar
constraint has many solutions.

The structs the probe was *not* being scored on moved just as decisively, which is
the real confirmation:

| struct | stock build | vendor build |
|---|---:|---:|
| `struct device` | 336 | 216 |
| `struct dev_pm_info` | 120 | 20 |
| `struct usb_device` | 728 | 600 |
| `struct usb_interface` | 392 | 272 |
| `struct wiphy` | 640 | 512 |
| `struct net_device` | 1112 | 984 |

## Measurement

Driver flags were left exactly as they were (`CONFIG_PLATFORM_GENERIC_ARM=y`,
`CONFIG_MP_INCLUDED=n`, `CONFIG_RTW_IPCAM_APPLICATION=y`, `EXTRA_CFLAGS += -Os`, …);
the only variable changed is which kernel the module is built against.

| | stock kernel.org 4.9.129 | **vendor 4.9.129** | shipped |
|---|---:|---:|---:|
| same-size functions | 3038 | **3497** | (3939 total) |
| semantically identical | 2197 (55.8%) | **2570 (65.2%)** | |
| identical bytes of `.text` | 365,924 (37.5%) | **423,356 (43.4%)** | |
| `.text` size | 1,005,464 (+3.04%) | **972,784 (−0.31%)** | 975,780 |
| module size | 1,953,988 (+35,932) | **1,904,016 (−14,040)** | 1,918,056 |
| `FUNC` symbols | 3874 | **3953** | 3970 |

`.text` overshooting by 3% and now undershooting by 0.3% is the same story the
function counts tell: the wrong kernel headers were inflating loads and address
arithmetic across the whole driver.

## What is left, and whose fault it is

### Gone: the kernel-header families

Three offset-correction families in the old histogram were kernel-driven, and all
three are now absent from the first 400 pairs:

| pair (rebuilt → shipped) | delta | sites, before | sites, after | what it was |
|---|---:|---:|---:|---|
| `1120 → 992` | −128 | 178 | **0** | `netdev_priv()`, i.e. `ALIGN(sizeof(struct net_device), 32)` |
| `260 → 252` | −8 | 14 | **0** | a field past the embedded `struct device` |
| `224 → 216` | −8 | 14 | **0** | ditto |

`proc_get_ldpc_cap` shows the fix in miniature — both binaries now open with the
identical pair `ldr r3,[r0,#72]` / `ldr r3,[r3,#992]`.

### Left: one driver struct, `+1312`

Aggregating the deltas over the top 400 pairs:

| delta | sites | | delta | sites |
|---:|---:|---|---:|---:|
| −2784 | 1054 | | +96 | 73 |
| +4096 | 714 | | +1216 | 28 |
| +1312 | 612 | | +160 | 22 |
| −32 | 195 | | +1152 | 21 |
| +32 | 182 | | +48 | 6 |
| +1344 | 169 | | +1264 | 5 |
| +1280 | 168 | | | |

These are not thirteen problems. ARM cannot encode a large offset in one `imm12`,
so GCC splits it into `add rX, rY, #<high>` plus a second `add`/`ldr` immediate, and
`offsetdiff.py` scores the halves separately. Every pair above recombines to the
same number:

```
+4096 + (−2784) = +1312      +1344 + (−32) = +1312      +1280 + (+32) = +1312
+1216 + (+96)   = +1312      +1152 + (+160) = +1312     +1264 + (+48) = +1312
```

More than 98% of the remaining struct-layout corrections are **one fact**.

`_rtw_read16` isolates it in five instructions:

```
shipped                                rebuilt
  add r3, r0, #4096                      add r3, r0, #4096
  add r0, r0, #7040                      add r0, r0, #5696
  add r0, r0, #4                         add r0, r0, #36
  ldr r3, [r3, #2960]                    ldr r3, [r3, #1648]
  bx  r3                                 bx  r3
```

`_rtw_read16` does `&adapter->iopriv.intf` then `intf.io_ops._read16`. So
`offsetof(_adapter, iopriv)` is **5728 in our build and 7040 in the shipped one**.
An offset probe compiled with the driver's own flags gives our side of the layout:

| member | our offset | our `sizeof` |
|---|---:|---:|
| `dvobj` | 20 | |
| `mlmepriv` | 24 | 2856 |
| `mlmeextpriv` | 2880 | 2296 |
| `cmdpriv` | 5176 | 84 |
| `evtpriv` | 5260 | 16 |
| `rmpriv` | 5276 | 452 |
| `iopriv` | 5728 | 88 |

The shift is bracketed on both sides. `dvobj` at 20 is unshifted — a `20 → 32`
family would appear if `CONFIG_SUPPORT_MULTI_BCN` were adding `_list list; u8 vap_id;`
to the head of `_ADAPTER`, and no such family exists. `mlmeextpriv` *is* shifted:
in `_issue_action_SM_PS` our `add r2, r4, #2880` is the shipped `add r2, r4, #4096`
(+108 = 4204, i.e. 2892 + 1312). Since `mlmepriv` starts at 24 in both and
`mlmeextpriv` starts 1312 bytes later in the shipped module, the growth is inside
`struct mlme_priv`: **2856 bytes here, 4168 bytes there.** Everything from
`mlmeextpriv` to the end of `_ADAPTER` — `HalData` at 15088 vs 16400,
`registrypriv` at 12408 vs 13720 — rides along on that one number.

`struct mlme_priv` is dense with `#ifdef`s (`CONFIG_RTW_MESH`, `CONFIG_RTW_MULTI_AP`,
`CONFIG_BEAMFORMING`, `CONFIG_AP_MODE`'s `wlan_acl_pool`, the roaming and 802.11r/k/v
blocks), so this is squarely **driver-`#ifdef`-driven, not kernel-driven** — it is
WP-C's problem, and WP-C now has a single scalar to hit rather than a histogram.

Everything else is noise. Once the `+1312` families are removed, no residual family
has more than three sites (`+304` and `+24`, three each), and the rest are one- and
two-site oddities clustered in `init_mlme_ext_priv`, `__nat25_db_network_insert`,
`init_channel_list` and `cfg80211_rtw_add_virtual_intf`. Several of those recombine
to *near* 1312 rather than exactly 1312 (`−2776`, `−2787`, `−2796` against `+4096`),
which is the signature of members being *reordered* inside a struct rather than the
struct being shifted — again consistent with a differing `#ifdef` rather than with
kernel headers.

## Reproducing

```sh
docker build --platform linux/arm64 -f build/Dockerfile.vendor \
             -t rtl8188fu-build-vendor:latest build/
docker run -d --platform linux/arm64 --name fuv \
    -v "$PWD":/src \
    -v /path/to/linux-4.9.129-fullhan-pristine:/vendor-src:ro \
    rtl8188fu-build-vendor:latest sleep infinity
docker exec fuv sh /build/prepare-vendor-kernel.sh     # copy + defconfig + modules_prepare
docker exec fuv sh /src/build/build.sh                 # KSRC=/build/linux-vendor from the image env
python3 build/offsetdiff.py /path/to/original/8188fu.ko ./8188fu.ko --pairs 30
```

The struct oracle, against the vendor kernel:

```sh
docker exec fuv sh -c 'cp -r /src/build/probe /tmp/probe &&
    make -C /build/linux-vendor M=/tmp/probe ARCH=arm CROSS_COMPILE=arm-linux-gnueabi- modules &&
    arm-linux-gnueabi-readelf -sW /tmp/probe/probe.ko | grep probe_'
```
