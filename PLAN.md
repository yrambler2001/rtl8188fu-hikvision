# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
SHA-256 `a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13`,
3,939 symbols / 975,780 bytes of `.text`.

## Measurement

* `build/fulldiff.py <shipped> <rebuilt> [--brief]` — whole-file scoreboard:
  every section, the symbol table, the relocations and the string tables.
  Current: **455 bytes still differ (0.024% of the file)**.
  *Caveat:* it strips GCC's `.NNNN` uniquifiers before comparing `.strtab`, so
  a `.strtab` scored 0 is not necessarily byte-identical. Use
  `build/oem/uidfn.sh` for that.
* `build/offsetdiff.py <shipped> <rebuilt> [--fn NAME]` — per-instruction
  operand diff of `.text`.
* `build/oem/run.sh [--fn NAME] [-v] [--score]` — the per-function loop: compile
  only the two OEM translation units and score all 46 functions in about a
  second. `--score` prints `n=<differing words>,d=<size delta>`.
* `build/oem/pub.sh <file.c> <fn> [-v]` — the same for one public file.
* `build/oem/uidfn.sh <file.c>` — the `__func__.NNNN` DECL_UID uniquifiers.
* `build/oem/dump.sh <unit> <gcc dump flags>` — GCC's own RTL/GIMPLE dumps.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | vendor compiler (`.comment` says `arm_multilib_uclibc_20200924`) | **solved** — stock GCC 6.5.0 rebuilt with that `--with-pkgversion`; `FINDINGS-toolchain.md` |
| 2 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** — `FINDINGS-vendor-kernel.md` |
| 3 | driver `#ifdef` configuration | **solved** — `FINDINGS-driver-config.md` |
| 4 | build path in `.rodata` via `__FILE__`, and `__DATE__`/`__TIME__` | **solved** — `FINDINGS-byte-gap.md` §3 |
| 5 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) | **reconstructed** — 42/46 byte-identical; `FINDINGS-oem-catalogue.md` |
| 6 | `DECL_UID` uniquifiers in `.symtab`/`.strtab` | **863/879 symbols** — `FINDINGS-oem-catalogue.md` §11 |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree / defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary *(done)* — the BSP's
  `fh8856v200_defconfig`, retargeted `CPU_V6` → `CPU_V7`
- **WP-C** driver `#ifdef` configuration *(done — `FINDINGS-driver-config.md`)*
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` *(done —
  `FINDINGS-oem-catalogue.md`)*: 28,368 → 455 bytes
- **WP-E** build under the original path *(done — `FINDINGS-byte-gap.md` §3)*
- **WP-F** GCC 6.5.0 with `--with-pkgversion='arm_multilib_uclibc_20200924'`
  *(done — `FINDINGS-toolchain.md`)*: `.comment` 9,347 → 0 bytes, and all 158
  object files byte-identical to the stock compiler's once `.comment` is removed
- **WP-G** the `__func__.NNNN` DECL_UID uniquifiers *(done, 863/879 —
  `FINDINGS-oem-catalogue.md` §11)*: the vendor's OEM header carried types and
  extern objects but not prototypes; splitting `include/ez_wifi.h` into
  `ez_wifi.h` + `ez_wifi_fn.h` took the mismatch from 726 symbols to 16

## Residuals

Four functions in `.text`, four ARM instructions in total, all of them register
allocation with a known cause (`FINDINGS-oem-catalogue.md` §10):

| function | delta | cause |
|---|---:|---|
| `process_config_vars` | +8 | the shipped build spills `pick`; IRA has 12 restricted allocnos to our 11 because our `n` does not cross the calls |
| `ez_scan_device_ioctl_handle` | +4 | `&probe_req_t` derived from the `.bss` section anchor rather than the literal pool |
| `ez_strsep` | 80 bytes, right size | one if-conversion, one loop-carried register |
| `ez_new_sc_ioctl` | 20 bytes, right size | a two-allocno tie IRA breaks the other way |

Plus 16 `__func__` uniquifiers in the two OEM files: the gap arithmetic in
`FINDINGS-oem-catalogue.md` §11 says the vendor's OEM sources declare 65 more
locals than ours. Those emit no code (the kernel builds with
`-Wno-unused-variable`), so the binary records their count and nothing else.
They are left as a measured residual rather than invented.

`.note.gnu.build-id` is an SHA-1 over the linked output and converges last.

## Closed in the last pass

`ez_device_info_ioctl_handle`, `ez_mac2u8`, `ez_wifi_func_poll_ioctl_handle`,
`ez_probe_requst_eid208_handler`, `ez_set_new_sc` and `rtw_efuse_analyze` all
became byte-identical; `process_config_vars` went +24 → +8 and
`ez_scan_device_ioctl_handle` +12 → +4. Three general rules came out of it and
are written up in `FINDINGS-oem-catalogue.md` §12–14:

1. **Block layout at `-Os` is source order.** GCC 6's
   `reorder_basic_blocks_simple` skips its edge sort entirely when optimising
   for size, so branch probabilities — including the very strong
   `PRED_COLD_FUNCTION` the kernel's `__cold` `printk` puts on every error path
   — are computed and then ignored.
2. **`uncprop` is type-sensitive.** It rewrites constants in PHI arguments into
   SSA names known to hold that constant, including a `switch` index on a
   single-valued case edge — but only when the types match. One `u32` that
   should have been `int` cost `ez_set_new_sc` 12 bytes.
3. **The `__func__.NNNN` uniquifiers are a declaration-count oracle**, and they
   also fix source order, which `.text` order cannot.

Each work package is done by one agent, which writes a markdown report into the
repo and commits it, so this file plus those reports are the full record.
