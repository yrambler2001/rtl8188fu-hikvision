# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
3939 functions / 975,404 bytes of `.text`.

Measurement: `build/offsetdiff.py <shipped> <rebuilt>`.
Current: **2570 / 3939 functions (65.2%) semantically identical**, 43.4% of `.text`.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (~54 functions) are not in the Realtek tarball | open - reconstruct from Hex-Rays |
| 2 | vendor compiler | **solved** - stock GCC 6.5.0 (kernel.org crosstool) matches |
| 3 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** - see `FINDINGS-vendor-kernel.md` |
| 4 | build path `/data1/jiangqifeng6/...` baked into `.rodata` by `WARN_ON` | open - trivial once 3 is closed |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree and/or its defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary using the offset oracle
  *(done)*: the Fullhan BSP's `fh8856v200_defconfig`, retargeted from `CPU_V6` to
  `CPU_V7`, hits all three oracle targets - `sizeof(struct module)==384`,
  `ALIGN(sizeof(net_device),32)==992`, `sizeof(struct iw_handler_def)==24` - and
  clears every kernel-header family out of the offset histogram.
- **WP-C** *(now the whole remaining offset problem)* `struct mlme_priv` is 2856
  bytes here and 4168 in the shipped module. That single +1312 shift of
  `offsetof(_ADAPTER, iopriv)` accounts for >98% of the surviving offset
  corrections. Find the driver `#ifdef` that adds 1312 bytes to `struct mlme_priv`
  (`CONFIG_RTW_MESH`, `CONFIG_RTW_MULTI_AP`, `CONFIG_BEAMFORMING`, ... are the
  candidates).
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` from `8188fu.ko.c` (Hex-Rays).
- **WP-E** build under the original path so `.rodata` `WARN_ON` strings match.

Each work package is done by one agent, which writes a markdown report into the repo
and commits it, so this file plus those reports are the full record.
