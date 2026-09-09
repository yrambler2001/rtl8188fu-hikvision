# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
3939 functions / 975,404 bytes of `.text`.

Measurement: `build/offsetdiff.py <shipped> <rebuilt>`.
Current: **3882 / 3939 functions (98.6%) semantically identical**, 97.3% of `.text`.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) are not in the Realtek tarball | open - reconstruct from Hex-Rays |
| 2 | vendor compiler | **solved** - stock GCC 6.5.0 (kernel.org crosstool) matches |
| 3 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** - see `FINDINGS-vendor-kernel.md` |
| 4 | build path `/data1/jiangqifeng6/...` baked into `.rodata` by `__FILE__` | open - trivial once someone builds under that path |
| 5 | driver `#ifdef` configuration | **solved** - see `FINDINGS-driver-config.md` |

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
- **WP-D** *(now the whole remaining problem)* reconstruct `ez_sc.c` / `ez_wifi_config.c`
  from `8188fu.ko.c` (Hex-Rays). 46 functions, ~9.6 KB of `.text`. Four functions in public
  files carry exact line-count constraints on the patch (`collect_bss_info` +61 lines in
  `rtw_mlme_ext.c`, `rtw_wx_set_priv` +2 in `ioctl_linux.c`, both efuse map writers +1 in
  `rtw_efuse.c`), and four more show where the OEM hooks were spliced in (`OnProbeReq`,
  `OnProbeRsp`, `rtw_ioctl`, `rtw_usb_primary_adapter_init`).
- **WP-E** build under the original path so `.rodata` `__FILE__` strings match.

Two single-function residues are recorded but unexplained: `_rtw_skb_alloc` (92 bytes; the
shipped module inlines an `__alloc_skb` fast path that no tarball `#ifdef` produces) and
`rtw_efuse_analyze` (4 bytes of register allocation). Both are detailed at the end of
`FINDINGS-driver-config.md`.

Each work package is done by one agent, which writes a markdown report into the repo
and commits it, so this file plus those reports are the full record.
