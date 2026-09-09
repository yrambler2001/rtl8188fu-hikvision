# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
3939 functions / 975,404 bytes of `.text`.

Measurement:

* `build/fulldiff.py <shipped> <rebuilt>` - whole-file scoreboard, every section, the
  symbol table, the relocations and the string tables. Current: **972 bytes still
  differ (0.051% of the file)**, and **34 of 41 sections are byte-identical**; see
  `FINDINGS-oem-catalogue.md`, `FINDINGS-byte-gap.md` and `FINDINGS-toolchain.md`.
* `build/offsetdiff.py <shipped> <rebuilt>` - per-instruction operand diff of `.text`.
* `build/oem/run.sh`, `build/oem/pub.sh` - the WP-D loop: compile only the two OEM
  translation units, or one public file, and score each function against the shipped
  module in seconds.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) are not in the Realtek tarball | **reconstructed** - 37/46 byte-identical, see `FINDINGS-oem-catalogue.md` |
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
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` *(done - `FINDINGS-oem-catalogue.md`)*.
  The two file names came out of the shipped `STT_FILE` symbols; their symbol grouping
  gave each file's `.text`/`.rodata`/`.data`/`.bss` ranges and so the 18/28 function
  split. Both files, their nine `.bss` and eight `.data` objects, all 115 strings, and
  the four public call sites (`rtw_ioctl`, `OnProbeReq`, `OnProbeRsp`,
  `rtw_usb_primary_adapter_init`) are reconstructed and wired in behind `CONFIG_EZ_WIFI`.
  **28,368 -> 972 bytes**; `.rodata.str1.1`, `.rodata`, `.data`, `.bss`, `.comment`,
  `.strtab`, `.ARM.exidx` and eleven of twelve relocation sections are now
  byte-identical, and `.symtab` has the right size and no missing or extra symbol. Nine
  OEM functions still differ, all by register allocation or block ordering; the
  catalogue lists each one and what is known about it.
- **WP-F** build GCC 6.5.0 with `--with-pkgversion='arm_multilib_uclibc_20200924'`
  *(done - `FINDINGS-toolchain.md`)*. `build/build-gcc-vendor.sh` rebuilds it from the FSF
  tarball with the kernel.org crosstool's own configure options plus that one string; no
  patches were needed. `.comment` went 9,347 -> **84** bytes (exactly the two OEM object
  files), the whole file 37,630 -> **28,368**, and codegen is untouched: all **158 object
  files are byte-identical** to the stock compiler's once `.comment` is removed, and
  `offsetdiff.py` still reports 3882/3939.

## Residuals

`_rtw_skb_alloc` (92 bytes) is **closed**: `FINDINGS-byte-gap.md` section 4.1's
reconstruction is correct, and it settles that note's open question in favour of an OEM
patch to `os_dep/osdep_service.c` rather than a patched `skbuff.h` - the same source
compiled against the same unmodified vendor headers reproduces the shipped function.
`rtw_sptime_get` is also closed; its 4-byte difference was the literal-pool alignment
`nop` section 4.3 predicted, and it disappeared once the OEM code moved the function.
`rtw_efuse_analyze` (4 bytes) remains, exactly as analysed in section 4.2.

Each work package is done by one agent, which writes a markdown report into the repo
and commits it, so this file plus those reports are the full record.
