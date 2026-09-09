# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
3939 functions / 975,404 bytes of `.text`.

Measurement:

* `build/offsetdiff.py <shipped> <rebuilt>` - per-instruction operand diff of `.text`.
  Current: **3882 / 3939 functions (98.6%) semantically identical**, 97.3% of `.text`.
* `build/fulldiff.py <shipped> <rebuilt>` - whole-file scoreboard, every section, the
  symbol table, the relocations and the string tables. Current: **28,368 bytes still
  differ (1.48% of the file)**; see `FINDINGS-byte-gap.md` and `FINDINGS-toolchain.md`.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) are not in the Realtek tarball | open - reconstruct from Hex-Rays |
| 2 | vendor compiler | **solved** - stock GCC 6.5.0 (kernel.org crosstool) matches |
| 3 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** - see `FINDINGS-vendor-kernel.md` |
| 4 | build path `/data1/jiangqifeng6/...` baked into `.rodata` by `__FILE__` | **solved** - see `FINDINGS-byte-gap.md` |
| 5 | driver `#ifdef` configuration | **solved** - see `FINDINGS-driver-config.md` |
| 6 | GCC's `--with-pkgversion` string, 159 copies in `.comment` | **solved** - see `FINDINGS-toolchain.md` |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree and/or its defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary using the offset oracle *(done)*:
  the Fullhan BSP's `fh8856v200_defconfig`, retargeted from `CPU_V6` to `CPU_V7`, hits all
  three oracle targets and clears every kernel-header family out of the offset histogram.
- **WP-C** driver `#ifdef` configuration *(done - `FINDINGS-driver-config.md`)*. The +1312
  growth of `struct mlme_priv` is `CONFIG_APPEND_VENDOR_IE_ENABLE`. Four more flags came
  out of the symbol-set diff: `CONFIG_POWER_SAVING = n`, `CONFIG_TXPWR_LIMIT_EN = y`,
  `CONFIG_AUTO_NOTCH_FILTER = y`, and `CONFIG_PLATFORM_OPS` must *not* be defined; plus
  `REALTEK_CONFIG_PATH = "/dav/"`. 65.2% -> 98.6%, and the offset histogram is now empty.
- **WP-E** build under the original path *(done - `FINDINGS-byte-gap.md` section 3)*.
  `build/build-vendorpath.sh` builds from
  `/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217`
  and pins `__DATE__`/`__TIME__` to `Dec 25 2023` / `20:43:27`. Every string our build
  emits is now present in the shipped module; zero path-like differences remain.
- **WP-D** *(now 99% of the remaining problem)* reconstruct `ez_sc.c` / `ez_wifi_config.c`
  from `8188fu.ko.c` (Hex-Rays). 46 functions, ~9.6 KB of `.text`, ~28 KB of the 37.6 KB
  whole-file gap. Constraints the binary already pins down:
  * four exact line counts on the patch (`collect_bss_info` +61 lines in `rtw_mlme_ext.c`,
    `rtw_wx_set_priv` +2 in `ioctl_linux.c`, both efuse map writers +1 in `rtw_efuse.c`);
  * four public functions carrying OEM call sites (`OnProbeReq` -176, `rtw_ioctl` -332,
    `OnProbeRsp` -12, `rtw_usb_primary_adapter_init` -8);
  * 115 OEM strings, byte for byte, from `fulldiff.py --strings`;
  * eight strings the OEM files duplicate from public files (`CN`, the vendor-IE messages);
  * one OEM file prints `__DATE__`/`__TIME__`, compiled at `20:43:30`;
  * exactly two `.comment` copies are missing, which is a third independent witness that
    the OEM code is two translation units and not one or three;
  * the OEM code calls `kernel_read`, `kmem_cache_alloc`/`kmalloc_caches` and
    `copy_to_user` (two extra out-of-line copies), none of which the public code reaches;
  * 8 `.data` objects, 9 `.bss` objects and 19 `__func__` constants, with exact sizes.
- **WP-F** build GCC 6.5.0 with `--with-pkgversion='arm_multilib_uclibc_20200924'`
  *(done - `FINDINGS-toolchain.md`)*. `build/build-gcc-vendor.sh` rebuilds it from the FSF
  tarball with the kernel.org crosstool's own configure options plus that one string; no
  patches were needed. `.comment` went 9,347 -> **84** bytes (exactly the two OEM object
  files), the whole file 37,630 -> **28,368**, and codegen is untouched: all **158 object
  files are byte-identical** to the stock compiler's once `.comment` is removed, and
  `offsetdiff.py` still reports 3882/3939.

## Residuals

`_rtw_skb_alloc` (92 bytes) and `rtw_efuse_analyze` (4 bytes) are still unexplained, and
`rtw_sptime_get` is confirmed to be identical code with one extra alignment `nop`. All
three are analysed in `FINDINGS-byte-gap.md` section 4 - including a disproof of the
previous `-fmerge-constants` explanation for `rtw_efuse_analyze`, and the exact C
reconstruction of the shipped `_rtw_skb_alloc`.

Each work package is done by one agent, which writes a markdown report into the repo
and commits it, so this file plus those reports are the full record.
