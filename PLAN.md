# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
SHA-256 `a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13`,
3,939 symbols / 975,780 bytes of `.text`.

## Measurement

* `build/fulldiff.py <shipped> <rebuilt> [--brief]` — whole-file scoreboard:
  every section, the symbol table, the relocations and the string tables.
  Current: **1,421 bytes still differ positionally (0.07% of the file)**, 228
  by the shift-tolerant "structural" count; 35 of the 41 sections are
  byte-identical.  *Compare attempts by the raw number:* the structural count
  charges a function whose size is wrong only its size delta and never looks
  inside it, so it can rate a worse state better.
  *Caveat:* it strips GCC's `.NNNN` uniquifiers before comparing `.strtab`, so
  a `.strtab` scored 0 is not necessarily byte-identical. Use
  `build/oem/uidgap.py` for that - it prints the DECL_UID oracle per interval.
* `build/offsetdiff.py <shipped> <rebuilt> [--fn NAME]` — per-instruction
  operand diff of `.text`.
* `build/oem/run.sh [--fn NAME] [-v] [--score]` — the per-function loop: compile
  only the two OEM translation units and score all 46 functions in about a
  second. `--score` prints `n=<differing words>,d=<size delta>`.
* `build/oem/pub.sh <file.c> <fn> [-v]` — the same for one public file.
* `build/oem/uidfn.sh <file.c>` — the `__func__.NNNN` DECL_UID uniquifiers.
* `build/oem/uidgap.py` — the same, paired against the shipped module and
  reported as a per-interval declaration deficit.
* `build/oem/dump.sh <unit> <gcc dump flags>` — GCC's own RTL/GIMPLE dumps;
  `SRCFILE=` runs them on a lab variant instead of the tree copy.
* `build/oem/gen.py --spec build/oem/specs/<f>.py --out build/oem/lab/<run>` —
  expand a spec's orthogonal axes into whole translation units, and
  `build/oem/lab.py --unit <u> --dir <run> --fn <f>` to compile and score them
  ten at a time. About thirty variants a second; roughly 27,000 went through
  it for the four remaining functions. Score by `s`, the register-blanked
  instruction edit distance, not by `n`.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | vendor compiler (`.comment` says `arm_multilib_uclibc_20200924`) | **solved** — stock GCC 6.5.0 rebuilt with that `--with-pkgversion`; `FINDINGS-toolchain.md` |
| 2 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** — `FINDINGS-vendor-kernel.md` |
| 3 | driver `#ifdef` configuration | **solved** — `FINDINGS-driver-config.md` |
| 4 | build path in `.rodata` via `__FILE__`, and `__DATE__`/`__TIME__` | **solved** — `FINDINGS-byte-gap.md` §3 |
| 5 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) | **reconstructed** — 42/46 byte-identical; `FINDINGS-oem-catalogue.md` |
| 6 | `DECL_UID` uniquifiers in `.symtab`/`.strtab` | **solved** — 879/879, `.strtab` byte-identical; `FINDINGS-oem-catalogue.md` §11 |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree / defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary *(done)* — the BSP's
  `fh8856v200_defconfig`, retargeted `CPU_V6` → `CPU_V7`
- **WP-C** driver `#ifdef` configuration *(done — `FINDINGS-driver-config.md`)*
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` *(done —
  `FINDINGS-oem-catalogue.md`)*: 28,368 → 1,421 bytes, 43/46 functions
  byte-identical
- **WP-E** build under the original path *(done — `FINDINGS-byte-gap.md` §3)*
- **WP-F** GCC 6.5.0 with `--with-pkgversion='arm_multilib_uclibc_20200924'`
  *(done — `FINDINGS-toolchain.md`)*: `.comment` 9,347 → 0 bytes, and all 158
  object files byte-identical to the stock compiler's once `.comment` is removed
- **WP-G** the `__func__.NNNN` DECL_UID uniquifiers *(done, 879/879 —
  `FINDINGS-oem-catalogue.md` §11)*: the vendor's OEM header carried types and
  extern objects but not prototypes; splitting `include/ez_wifi.h` into
  `ez_wifi.h` + `ez_wifi_fn.h` took the mismatch from 726 symbols to 16, a
  third source-order fix (`ez_probe_req_handler`) and one dropped local closed
  the two intervals that were *over*, and the 65 declarations the oracle still
  demands - which emit no code and so cannot be identified, only counted - are
  labelled placeholders of exactly the right size in exactly the right
  intervals. `.strtab` is byte-identical
- **WP-H** the variant search *(done — `build/oem/gen.py`, `lab.py`,
  `specs/`)*: generate semantically-neutral spellings mechanically and score
  them against the shipped bytes, instead of hand-guessing C shapes

## Residuals

**1,421 bytes.** Three functions in `.text`, all of them now the *right size*,
each a register-allocation tie with a mechanism identified exactly
(`FINDINGS-oem-catalogue.md` §10, §17–19):

| function | differs by | cause |
|---|---:|---|
| `process_config_vars` | 49 words of 86 | the register allocation now matches — `stm sp, {r2, r3}`, `pick` spilled, twelve call-crossing allocnos — which needed `n` live across the two calls, which needed VRP's `register_edge_assert_for` not to assert `n == 0` from the loop guard. What is left is which register IRA picked, and one instruction: every guard spelling that blocks the assertion needs a separate compare where the shipped build has one `orrs` |
| `ez_new_sc_ioctl` | 5 words of 14 | an IRA preference tie broken by `rq`'s weight-125 preference for r2 |
| `ez_strsep` | 4 words of 39 | the shipped build routes the delimiter path through the shared `*stringp` store; ours fuses the NUL store into a post-increment and does its own |

Where the bytes are: `.text` 1,002 (208 structural), `.note.gnu.build-id` 20
(an SHA-1 over the linked output, converges last), and 399 bytes of relocation
addends and branch displacements inside those three functions.  `.symtab`,
`.strtab` and every relocation section are byte-identical.

## Rules learned, and where they are written up

`FINDINGS-oem-catalogue.md` §12–18:

1. **Block layout at `-Os` is source order.** GCC 6's
   `reorder_basic_blocks_simple` skips its edge sort entirely when optimising
   for size, so branch probabilities — including the very strong
   `PRED_COLD_FUNCTION` the kernel's `__cold` `printk` puts on every error path
   — are computed and then ignored.
2. **`uncprop` is type-sensitive**, and **a typedef of `int` is not `int`**:
   `pushdecl` gives every named typedef its own variant type node, and
   `uncprop` and `gimple_can_coalesce_p` compare `TREE_TYPE` *pointers*. `int`
   and `s32` compile differently even though `__builtin_types_compatible_p`
   says they are the same. §13, §15.
3. **The `__func__.NNNN` uniquifiers are a declaration-count oracle**, and they
   also fix source order, which `.text` order cannot. §11 has the full
   accounting table (what each construct costs in DECL_UIDs).
4. **Score by structure, not by bytes.** A variant that is right except for
   which registers IRA picked differs in nearly every word; the useful
   gradient is the instruction-sequence edit distance with the register fields
   blanked out. §9.

Each work package is done by one agent, which writes a markdown report into the
repo and commits it, so this file plus those reports are the full record.
