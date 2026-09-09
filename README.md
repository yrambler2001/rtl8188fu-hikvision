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

That is the quick path, against a kernel.org 4.9.129. The build that produces the numbers
below uses the Fullhan vendor kernel (`build/Dockerfile.vendor`), the vendor's own build
path and timestamp (`build/build-vendorpath.sh`), and a GCC 6.5.0 rebuilt with the vendor's
`--with-pkgversion` (`build/build-gcc-vendor.sh`, one command, ~13 min).

## Result

With the exact compiler, the exact kernel, the recovered `#ifdef` set, the vendor's
own build path and the two reconstructed OEM translation units, the module now
reproduces to within **0.068%**.

| metric | result |
|---|---|
| `vermagic` | **exact match** — `4.9.129 mod_unload ARMv7 p2v8` |
| ARM ELF attributes | **identical** (all 15 tags) |
| `.modinfo` | **byte-identical** (9,246 bytes: params, descriptions, alias, version) |
| compiled source files | **159 / 159** — the two OEM files are reconstructed (`FINDINGS-oem-catalogue.md`) |
| function symbols | **3909 / 3909**, none missing, none extra |
| same-size functions | **3901 / 3909** |
| **whole file** | **1,296 of 1,918,056 bytes still differ (0.068%)** |
| byte-identical sections | **34 / 41**, including `.rodata.str1.1`, `.rodata`, `.data`, `.bss`, `.comment`, `.strtab` and eleven of the twelve relocation sections |
| what is left | nine OEM functions differing only by register allocation or block ordering, one 4-byte public residual, and the build-id hash |

Those figures are against the **Fullhan vendor kernel** (`build/Dockerfile.vendor`,
`FINDINGS-vendor-kernel.md`) with the recovered driver configuration
(`FINDINGS-driver-config.md`) and the rebuilt compiler (`FINDINGS-toolchain.md`). Against a stock kernel.org 4.9.129 the same source gave
3817 symbols / 3038 same-size / 2181 byte-identical (55.4%); with the vendor kernel but
the wrong driver `#ifdef`s, 2570 (65.2%).

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
  lands in `.comment` and affects nothing else — now proven, not assumed:
  `build/build-gcc-vendor.sh` rebuilds GCC 6.5.0 with the crosstool prebuilt's
  own configure options plus that string, and all 158 object files it produces
  are byte-identical to the stock compiler's once `.comment` is removed
  (`FINDINGS-toolchain.md`). The compiler underneath is stock GCC 6.5.0.
* `nolibc` is correct. Kernel modules are freestanding — they never link libc,
  so the uclibc/glibc distinction cannot reach codegen.

### What still differs, and why

Four functions are the right size but not bit-identical, and seven differ in size.
That is down from 857 same-size-but-differing at the start of the vendor-kernel work,
where the differing instruction words classified as:

| share | kind |
|---:|---|
| 36.6% | `ldr`/`str` where **only the immediate offset differs** |
| 35.0% | same opcode, different operand |
| 18.7% | different opcode |
| 9.7% | `ldr`/`str`, other field |

A load/store that differs *only* in its immediate offset is a struct field at a
different offset. That was the signature of **different kernel headers** — the
vendor's patched 4.9.129 tree and its `.config` (`FINDINGS-vendor-kernel.md`) — and then
of one driver `#ifdef`, `CONFIG_APPEND_VENDOR_IE_ENABLE`, which makes `struct mlme_priv`
1312 bytes larger and shifts everything after it in `_ADAPTER`
(`FINDINGS-driver-config.md`). With both fixed, **not one `ldst` immediate differs
anywhere in the module**. What remains is the 46 OEM functions, four functions whose only
difference is a `__LINE__` constant, and two single-function oddities.

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
| `CONFIG_APPEND_VENDOR_IE_ENABLE = y` | `sizeof(struct mlme_priv) == 4168`; `rtw_vendor_ie_*` symbols |
| `CONFIG_POWER_SAVING = n` | 40 LPS/IPS functions absent; every `CONFIG_LPS`/`CONFIG_IPS`-guarded string absent |
| `CONFIG_TXPWR_LIMIT_EN = y` | `rtw_tx_pwr_lmt_enable` is in `.data` with value 1 |
| `CONFIG_AUTO_NOTCH_FILTER` defined | `phy_SpurCalibration_8188F` is 220 bytes shorter |
| `CONFIG_PLATFORM_OPS` **not** defined | binary has `platform_wifi_power_on`/`_off` |
| `REALTEK_CONFIG_PATH = "/dav/"` | `rtw_phy_file_path` resolves to that string |

On per the symbol table: 80211K, WNM, MBO, 80211R, BTM_ROAM, IOCTL_CFG80211, LAYER2_ROAMING,
IEEE80211W, 80211D, PROC_DEBUG, BR_EXT, NAPI, GRO, NETIF_SG, AP + NATIVEAP_MLME, P2P, WFD,
radiotap/monitor. Off: MESH, MULTI_AP, CONCURRENT, MCC, TDLS, BT_COEXIST, BEAMFORMING,
80211AC_VHT, WAPI, MP. Derivation and evidence in `FINDINGS-driver-config.md`.
