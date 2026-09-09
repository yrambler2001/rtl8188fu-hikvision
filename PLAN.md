# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
3939 functions / 975,404 bytes of `.text`.

Measurement: `build/offsetdiff.py <shipped> <rebuilt>`.
Current: **2197 / 3939 functions (55.8%) semantically identical**, 37.5% of `.text`.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (~54 functions) are not in the Realtek tarball | open - reconstruct from Hex-Rays |
| 2 | vendor compiler | **solved** - stock GCC 6.5.0 (kernel.org crosstool) matches |
| 3 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | open - dominant cause of remaining diffs |
| 4 | build path `/data1/jiangqifeng6/...` baked into `.rodata` by `WARN_ON` | open - trivial once 3 is closed |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree and/or its defconfig *(running)*
- **WP-B** recover the kernel `.config` from the binary using the offset oracle:
  hit `sizeof(struct module)==384`, `ALIGN(sizeof(net_device),32)==992`,
  `sizeof(struct iw_handler_def)==24`, and drive the offset histogram to empty.
  Prefer rebasing off a minimal config rather than `multi_v7_defconfig`.
- **WP-C** explain the non-kernel offset corrections (`+4096` at 491 sites,
  `+1312/+1280/+1344`, `+/-32`) - these look like *driver* `#ifdef` flags
  (`CONFIG_BT_COEXIST`, `CONFIG_MP_INCLUDED`, `CONFIG_RTW_DEBUG`, ...), not kernel headers.
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` from `8188fu.ko.c` (Hex-Rays).
- **WP-E** build under the original path so `.rodata` `WARN_ON` strings match.

Each work package is done by one agent, which writes a markdown report into the repo
and commits it, so this file plus those reports are the full record.
