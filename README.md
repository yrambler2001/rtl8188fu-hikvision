# rtl8188fu-repro

Reconstructed source + reproduction build for the `8188fu.ko` shipped in a
Hikvision IP camera firmware (`root_b240427`).

## What the binary told us

The module is unstripped, so it carries its own provenance:

| | |
|---|---|
| `version` | `v5.15.3-6-g1a2e952f9.20230217` |
| `author` | Realtek Semiconductor Corp. |
| `alias` | `usb:v0BDApF179...` → RTL8188FTV/FU (`0bda:f179`) |
| `vermagic` | `4.9.129 mod_unload ARMv7 p2v8` |
| `.comment` | `GCC: (arm_multilib_uclibc_20200924) 6.5.0` |
| build path | `/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/` |
| ARM attrs | CPU v7-A, FP VFPv2, no `Tag_ABI_VFP_args` (soft-float ABI), `Tag_ABI_optimization_goals: Aggressive Size` (= `-Os`) |

## History

Realtek's real git is internal and not public — GitHub's commit index has zero
hits for `1a2e952f9`. Every public "rtl8188fu" repo begins with a tarball
import. The popular ones (ulli-kroll 460 commits, kelebek333 130) are on the
2017 `v4.3.23.6` codebase, a different driver generation.

So this repo reconstructs a **release lineage** instead: one commit per Realtek
drop, in date order.

```
v5.11.5      OpenIPC/realtek-wlan
v5.11.5.2    OpenIPC/realtek-wlan
v5.11.5.4    OpenIPC/realtek-wlan   (v5.11.5.4-0-g65b8f0aad.20220413)
v5.15.3      pristine vendor tarball  <-- source of the shipped binary
```

`git log -p --follow <file>` and `git blame` work at release granularity.

## Build

```sh
cd build && docker build --platform linux/arm64 -t rtl8188fu-build .
cd .. && docker run --rm --platform linux/arm64 -v "$PWD":/src -w /src \
           rtl8188fu-build sh build/build.sh
build/compare.sh /path/to/original/8188fu.ko
```

## Result

Byte-exact is **not reachable** — see below. What the build does achieve:

| metric | result |
|---|---|
| `vermagic` | **exact match** — `4.9.129 mod_unload ARMv7 p2v8` |
| ARM ELF attributes | **identical** (all 15 tags) |
| `__param` section | **byte-identical** (2460 bytes) |
| compiled source files | **157 / 159** (missing only the two OEM files) |
| function symbols | **3790 / 3939 = 96.2%** |
| module size | 1,944,320 vs 1,918,056 (+1.37%) |

The 149 functions present only in the original break down as:

- **63** GCC inlining artifacts (`.constprop.N` / `.part.N` / `.isra.N`)
- **~54** OEM Hikvision/EZVIZ code (`ez_*`, `rtw_ezviz_ie_set`, `rtw_vendor_ie_*`,
  `set_smartconfig_flag`, `woal_is_*_country`, …)
- **27** static helpers GCC 10 inlined but GCC 6.5 kept out of line
  (`IS_MCAST`, `__div64_32`, `copy_from_user`, `tasklet_schedule`, …)
- **8** unexplained (`__nat25_*`, `platform_wifi_power_on/off`,
  `hal_EfusePgPacketWrite2ByteHeader`, `rtw_cfg80211_set_auth_type`, `dump_rx_packet`)

## Why byte-exact is impossible

1. **Two source files do not exist publicly.** `ez_sc.c` and `ez_wifi_config.c`
   are OEM SmartConfig code — ~30 functions, plus vendor-IE patches spliced into
   stock Realtek files. They exist only in the decompilation.
2. **The compiler is not obtainable.** `arm_multilib_uclibc_20200924` GCC 6.5.0
   is a vendor-built toolchain; it was never published. GCC codegen is not
   portable across versions, so `.text` will differ regardless.
3. **The kernel tree is not the vanilla one.** vermagic says 4.9.129, but the
   vendor's tree is patched and its `.config` is unknown; struct layouts in
   `include/generated/autoconf.h` feed directly into codegen.
4. **The build path is embedded.** `WARN_ON` strings bake in
   `/data1/jiangqifeng6/...`, so even identical code yields different `.rodata`
   unless the path is recreated exactly.

Items 2–4 are reproducible in principle with the vendor's SDK. Item 1 is not
recoverable from anything public — it would have to come from a GPL source
request to the device vendor.

## Recovered vendor build settings

Derived from the binary, applied to the Makefile in the build commit:

| setting | evidence |
|---|---|
| `-Os` (not Realtek's default `-O1`) | `Tag_ABI_optimization_goals: Aggressive Size` |
| `CONFIG_MP_INCLUDED = n` | `rtw_mp.o`, `ioctl_mp.o` absent |
| `CONFIG_WAPI_SUPPORT = n` | `rtw_wapi.o` absent |
| `CONFIG_RTW_IPCAM_APPLICATION = y` | force-enables monitor; binary has `rtw_recv_monitor` |
| `CONFIG_WIRELESS_EXT` in kernel | binary has the `rtw_wx_*` handlers |
| USB-only, ARMv7 | no `platform_*_sdio.o`; ARM attrs |

Enabled per the object list: MESH, 80211K, WNM, MBO, IOCTL_CFG80211, CFG_VENDOR,
TDLS, BT_COEXIST, MCC, BEAMFORMING, PROC_DEBUG, BR_EXT, ANDROID, AP, P2P, radiotap.
