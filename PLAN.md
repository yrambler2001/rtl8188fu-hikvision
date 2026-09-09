# Plan: byte-exact reproduction of the shipped `8188fu.ko`

Reference: the shipped `8188fu.ko`, 1,918,056 bytes,
SHA-256 `a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13`,
3,939 symbols / 975,780 bytes of `.text`.

## Measurement

* `build/fulldiff.py <shipped> <rebuilt> [--brief]` — whole-file scoreboard:
  every section, the symbol table, the relocations and the string tables.
  Current: **0 bytes differ**; 41 of the 41 sections are byte-identical and
  `cmp` is silent.  *While anything still differs, compare attempts by the raw
  number:* the structural count charges a function whose size is wrong only
  its size delta and never looks inside it, so it can rate a worse state
  better.
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
  ten at a time. About fifteen variants a second; roughly 100,000 went through
  it for the last three functions. Score by `s`, the register-blanked
  instruction edit distance, not by `n`. *Caveat:* a spec axis passed through
  the environment is split on `|`, so a guard expression containing `|` must
  be written into the spec, not exported - one 34,560-variant run was wasted
  that way.
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
| 5 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) | **reconstructed** — 46/46 byte-identical; `FINDINGS-oem-catalogue.md` |
| 6 | `DECL_UID` uniquifiers in `.symtab`/`.strtab` | **solved** — 879/879, `.strtab` byte-identical; `FINDINGS-oem-catalogue.md` §11 |

## Work packages

- **WP-A** find the Fullhan FH865X Linux 4.9.129 tree / defconfig *(done)*
- **WP-B** recover the kernel `.config` from the binary *(done)* — the BSP's
  `fh8856v200_defconfig`, retargeted `CPU_V6` → `CPU_V7`
- **WP-C** driver `#ifdef` configuration *(done — `FINDINGS-driver-config.md`)*
- **WP-D** reconstruct `ez_sc.c` / `ez_wifi_config.c` *(done —
  `FINDINGS-oem-catalogue.md`)*: 28,368 → 0 bytes, 46/46 functions
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

**None.**  `cmp` is silent, both files hash to
`a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13`, and all 41
sections are byte-identical.  `build/verify.sh` reproduces that from a clean
`git archive` of HEAD and confirms two consecutive builds agree.

The last four, and what closed each (`FINDINGS-oem-catalogue.md` §17, §18,
§21):

| | mechanism | closed by |
|---|---|---|
| `ez_strsep` | TER sank `q + 1` past the NUL store and `auto-inc-dec` folded the pair into a post-increment | a TER-opaque store |
| `ez_new_sc_ioctl` | IRA's colouring order is `ALLOCNO_FREQ`, i.e. 1000 × the RTL reference count at `-Os`; `rq` had three references and `is_null` two | two empty `asm`s on `is_null` |
| `process_config_vars`, `m` | `tree-ssa-dom.c`'s `record_edge_info` boolean special case folds the loop PHI's argument to 1 and the cstore dies | `_Bool m` + `(end == 0) & (m & 1)` |
| `process_config_vars`, `pos` | seven per-edge `pos = 0` copies let out-of-SSA coalesce the guard temp into pos's partition, and `reorder_basic_blocks_simple` then gave the loop tail to the wrong predecessor | one shared `pos = 0` in a block kept alive by an `asm` that uses it |

Two more register assignments in `process_config_vars` (`end` over `j`, the
guard temp over `buf`) were the same reference-count rule as
`ez_new_sc_ioctl` and needed the same device.

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
11. **IRA's colouring order is the reference count.** `assign_hard_reg` runs
    in the order `push_allocnos_to_stack` unwinds, which is
    `bucket_allocno_compare_func`'s sort, whose first key is `ALLOCNO_FREQ` —
    and `REG_FREQ_FROM_BB` is the constant `REG_FREQ_MAX` whenever
    `optimize_function_for_size_p`, so at `-Os` `ALLOCNO_FREQ` is exactly
    1000 × the number of times the pseudo appears in the RTL. The allocno with
    *fewer* references is coloured *last*. A corollary: block frequencies do
    not exist at `-Os`, so `unlikely()` cannot move an allocation tie at all.
    §21
12. **`uncprop` is bounded by `gimple_can_coalesce_p`.** It rewrites a
    constant PHI argument into an equivalent SSA name only if that name can
    coalesce with the PHI *result*, which needs `TREE_TYPE` pointer equality or
    an equal `TYPE_CANONICAL` plus `types_compatible_p`. That is the lever for
    a coalescing residual — and it is also why it has side effects, because the
    constant copies it stops suppressing become real blocks that cross-jumping
    and `reorder_basic_blocks_simple` then move. §17
13. **`auto-inc-dec` has a `dbg_cnt`.** `-fdbg-cnt=auto_inc_dec:N` blocks one
    fold and leaves the others, which is how TER and `auto_inc_dec` were
    separated in `ez_strsep` instead of being argued about. Register
    allocation has no such counter — `grep dbg_cnt ira-*.c` is empty. §18
14. **`reorder_basic_blocks_simple` is first-come-first-served in block-chain
    order.** At `-Os` it does not sort at all: it walks `FOR_EACH_BB_FN`,
    collects each block's single-successor edge (or a condjump's fallthrough
    and taken edges, fallthrough first), and makes each one a fallthrough if
    both ends are still free chain endpoints. So the loop tail goes to the
    *first* single-successor predecessor in chain order, and the chains are
    then emitted in the order of their start blocks. Nothing about
    probabilities enters into it. §17
15. **A shared tail written once does not stay one block.** `pos = 0` reached
    by `goto` from six arms is DCE'd into the PHI argument, the block becomes
    an empty forwarder, and `cleanup_cfg` deletes it — putting the copy back on
    all six edges. Keeping the block needs a real *use* of the stored value.
    §17
16. **Cross-jumping matches a constant against a register.** `can_replace_by`
    in `cfgcleanup.c` accepts two sets of the same destination when one source
    is a `CONST_INT` and the other carries an equal `REG_EQUAL`, which is how a
    `pos = n` in one arm gets merged into a shared `pos = 0`. It does not match
    an `asm`, so the order of statements inside the shared block decides
    whether the merge happens. §17
17. **DOM folds a boolean-ranged branch operand into successor PHIs.**
    `record_edge_info` records `x == 1` on the true edge of `if (x != 0)`
    whenever `ssa_name_has_boolean_range (x)` — which is true for an `int`
    whose nonzero bits are 1 — and `cprop_into_successor_phis` deliberately
    applies edge equivalences to PHIs in *non-dominated* blocks. That is what
    kills a materialised 0/1 flag; the decision is keyed on the PHI's type, so
    `_Bool` escapes it and no `int` spelling does. §17

Each work package is done by one agent, which writes a markdown report into the
repo and commits it, so this file plus those reports are the full record.
