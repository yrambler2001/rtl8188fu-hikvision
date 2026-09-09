# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: `/path/to/8188fu.ko`, 1,918,056 bytes,
SHA-256 `a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13`,
3,939 symbols / 975,780 bytes of `.text`.

## Measurement

* `build/fulldiff.py <shipped> <rebuilt> [--brief]` — whole-file scoreboard:
  every section, the symbol table, the relocations and the string tables.
  Current: **121 bytes still differ positionally (0.0063% of the file)**, 228
  by the shift-tolerant "structural" count; 39 of the 41 sections are
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
  ten at a time. About fifteen variants a second; roughly 70,000 went through
  it for the three remaining functions. Score by `s`, the register-blanked
  instruction edit distance, not by `n`.
* `build/oem/align.py <fn> [--obj FILE]` — the two instruction streams aligned
  by that same edit distance and printed side by side, so what is structurally
  different is one glance rather than an inference. Works against an object or
  against the linked module.

## Barriers

| # | barrier | status |
|---|---|---|
| 1 | vendor compiler (`.comment` says `arm_multilib_uclibc_20200924`) | **solved** — stock GCC 6.5.0 rebuilt with that `--with-pkgversion`; `FINDINGS-toolchain.md` |
| 2 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **solved** — `FINDINGS-vendor-kernel.md` |
| 3 | driver `#ifdef` configuration | **solved** — `FINDINGS-driver-config.md` |
| 4 | build path in `.rodata` via `__FILE__`, and `__DATE__`/`__TIME__` | **solved** — `FINDINGS-byte-gap.md` §3 |
| 5 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) | **reconstructed** — 43/46 byte-identical, all 46 at the shipped address and size; `FINDINGS-oem-catalogue.md` |
| 6 | `DECL_UID` uniquifiers in `.symtab`/`.strtab` | **solved** — 879/879, `.strtab` byte-identical; `FINDINGS-oem-catalogue.md` §11 |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree / defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary *(done)* — the BSP's
  `fh8856v200_defconfig`, retargeted `CPU_V6` → `CPU_V7`
- **WP-C** driver `#ifdef` configuration *(done — `FINDINGS-driver-config.md`)*
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` *(done —
  `FINDINGS-oem-catalogue.md`)*: 28,368 → 121 bytes, 43/46 functions
  byte-identical, all 46 at the shipped address and size
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

**121 bytes**, in three functions and the build-id that hashes them. All three
are the *right size* and at the *right address*; each is one named GCC decision
(`FINDINGS-oem-catalogue.md` §17, §18, §21):

| | bytes | words | edit distance | cause |
|---|---:|---:|---:|---|
| `process_config_vars` | 79 | 44 of 86 | 5 | `uncprop` rewrites all seven main-path `pos = 0` PHI arguments into the guard temp and out-of-SSA's coalesce costs accumulate per edge, so the temp is coalesced into pos's partition and pos needs a second register plus a latch copy; and the shipped build materialises `m` with a dead cmov pair where VRP lets ours branch straight to the shared `m = 1` |
| `ez_new_sc_ioctl` | 17 | 5 of 14 | 2 | an IRA tie: `rq` and `is_null` both prefer r1 at weight 2000 and cancel, and `rq`'s weight-125 preference for r2 — because it dies in `add r2, rq, #16` — decides |
| `ez_strsep` | 6 | 4 of 39 | 2 | TER moves `q + 1` to its single use, `auto_inc_dec` then folds it into `strb r3, [r4], #1`, and the two `*stringp` stores stop being the same instruction |
| `.note.gnu.build-id` | 19 | | | an SHA-1 over the linked output |

Everything else is byte-identical: `.rodata`, `.rodata.str1.1`, `.data`,
`.bss`, `.symtab`, `.strtab`, `.modinfo`, `.comment`, all twelve relocation
sections and all four exidx sections — 39 of 41. Every function symbol is at
the shipped address with the shipped size.

### The two-count trap, twice

`fulldiff.py`'s structural count charges a wrong-sized function only its size
delta; `oemdiff.py` compares an object to the linked module *symbolically*,
masking relocated words and branch displacements. Both are necessary and both
under-report. Four functions that were byte-identical in content but in the
wrong `.text` *position* passed every per-function check while costing 1,280
bytes across five sections; a plain `cmp` of the two modules, bucketed by
symbol, is the check that finds that (`FINDINGS-oem-catalogue.md` §20).

## Rules learned, and where they are written up

`FINDINGS-oem-catalogue.md` §12–21:

1. **Block layout at `-Os` is source order.** GCC 6's
   `reorder_basic_blocks_simple` skips its edge sort entirely when optimising
   for size, so branch probabilities — including the very strong
   `PRED_COLD_FUNCTION` the kernel's `__cold` `printk` puts on every error path
   — are computed and then ignored. §12
2. **`.text` order is the *call graph*, not the source.** GCC emits functions
   in the reverse of `ipa_reverse_postorder`, a depth-first walk over callers,
   so a function drags its callees in front of it and one misplaced root moves
   a whole chain. That, and not any content difference, was 1,280 of the last
   1,421 bytes. §20
3. **A per-function harness that compares symbolically cannot see a placement
   error.** `oemdiff.py` masks relocated words and branch displacements, so
   four functions in the wrong place scored clean. Check the linked module
   positionally too, bucketed by symbol. §10, §20
4. **`uncprop` is type-sensitive**, and **a typedef of `int` is not `int`**:
   `pushdecl` gives every named typedef its own variant type node, and
   `uncprop` and `gimple_can_coalesce_p` compare `TREE_TYPE` *pointers*. `int`
   and `s32` compile differently even though `__builtin_types_compatible_p`
   says they are the same. §13, §15
5. **Out-of-SSA's coalesce costs accumulate per edge.** `add_coalesce` adds,
   it does not take a maximum, so a value that reaches a PHI on seven edges
   beats one that reaches it on two — which is why the guard temp, and not
   `pos` itself, wins pos's register in `process_config_vars`. §17
6. **VRP's `register_edge_assert_for` recurses into an IOR's operands
   unconditionally at the top level, but the recursion one level down is gated
   on `has_single_use`.** Nesting the IOR is therefore the way to keep a flag
   live across a call while still emitting one `orrs`. §17
7. **TER moves an expression to its single use**, which decides whether
   `auto_inc_dec` — whose backwards scan only looks for an inc *after* the
   memory reference — can fold an address computation into a post-increment.
   §18
8. **The `__func__.NNNN` uniquifiers are a declaration-count oracle**, and they
   constrain source order, which `.text` order alone does not. §11 has the full
   accounting table (what each construct costs in DECL_UIDs).
9. **Score by structure, not by bytes.** A variant that is right except for
   which registers IRA picked differs in nearly every word; the useful
   gradient is the instruction-sequence edit distance with the register fields
   blanked out — `build/oem/align.py` prints the alignment. §9
10. **Read IRA's own numbers.** `-fira-verbose=9` prints every allocno, its
    conflicts and its hard-register preferences with weights, which turns
    "guess a shape" into "read the decision". §21

Each work package is done by one agent, which writes a markdown report into the
repo and commits it, so this file plus those reports are the full record.
