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

Byte-exact for the whole module is not reachable (see below), but with the
**exact compiler** the majority of the driver now reproduces bit-for-bit.

| metric | result |
|---|---|
| `vermagic` | **exact match** — `4.9.129 mod_unload ARMv7 p2v8` |
| ARM ELF attributes | **identical** (all 15 tags) |
| compiled source files | **157 / 159** (missing only the two OEM files) |
| function symbols present | **3872 / 3939 = 98.3%** |
| same-size functions | **3497 / 3872 = 90.3%** |
| **byte-identical functions** | **2570 = 65.2% of the module, 43.4% of `.text`** |
| module size | 1,904,016 vs 1,918,056 shipped (−0.7%) |

Those figures are against the **Fullhan vendor kernel** (`build/Dockerfile.vendor`,
`FINDINGS-vendor-kernel.md`). Against a stock kernel.org 4.9.129 the same source
gives 3817 symbols / 3038 same-size / 2181 byte-identical (55.4%).

"Byte-identical" masks two things that encode link layout rather than code:
relocated operands, and ARM `B`/`BL` displacements the assembler resolved
inside `.text`. Run `build/bytecompare.py <original.ko>` to reproduce.

### What matching the compiler bought

| | Debian GCC 10.2.1 | **GCC 6.5.0 (exact)** |
|---|---|---|
| function symbol coverage | 96.2% | **96.9%** |
| unmatched inlining artifacts | 63 | **39** |
| byte-identical functions | ~0 | **2181 (55.4%)** |

The toolchain came from kernel.org's crosstool prebuilts:
`arm64-gcc-6.5.0-nolibc-arm-linux-gnueabi`. Two things make this legitimate
rather than an approximation:

* `arm_multilib_uclibc_20200924` is only GCC's `--with-pkgversion=` string. It
  lands in `.comment` and affects nothing else. The compiler underneath is
  stock GCC 6.5.0.
* `nolibc` is correct. Kernel modules are freestanding — they never link libc,
  so the uclibc/glibc distinction cannot reach codegen.

### What still differs, and why

Of the 857 functions that are the right size but not bit-identical, the
differing instruction words classify as:

| share | kind |
|---:|---|
| 36.6% | `ldr`/`str` where **only the immediate offset differs** |
| 35.0% | same opcode, different operand |
| 18.7% | different opcode |
| 9.7% | `ldr`/`str`, other field |

A load/store that differs *only* in its immediate offset is a struct field at a
different offset. That was the signature of **different kernel headers** — the
vendor's patched 4.9.129 tree and its `.config`. Building against that tree removed
every kernel-header offset family; what survives is a single driver-side one, a
+1312-byte `struct mlme_priv`. See `FINDINGS-vendor-kernel.md`.

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
