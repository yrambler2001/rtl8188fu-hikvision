# Techniques carried over from a sibling reconstruction project

Source: **a sibling byte-exact ARM reconstruction project (private)** — a different target, a
different vendor, the same discipline of driving a reconstruction by scoring compiler output
against shipped bytes. Nothing of that project is reproduced here. What follows is the set of
*mechanisms* it had already established, restated in this project's terms, with what this project
independently measured about each. Every mechanism named below is a fact about GCC, checkable
against the GCC source tree this project already has unpacked, and the ones that mattered were
checked that way here before being relied on.

Target, at the time this was written: the 121 bytes still differing in `8188fu.ko` —
`process_config_vars` (79 B), `ez_new_sc_ioctl` (17 B), `ez_strsep` (6 B), `.note.gnu.build-id`
(19 B). **All four have since closed**: the module is byte-exact. `README.md` §4 records what
closed each. These notes are kept as they were written, at the point of transfer, rather than
retrofitted to the answer — the value of a transfer note is that it says what was believed
*before* the residual fell.

**Version caveat, applies to everything below.** The sibling project is on GCC 4.9.3 and 5.4.1;
8188fu is GCC 6.5.0. Every pass named below exists in 6.5.0, but some behaviour moved between
those releases, and `reorder_basic_blocks_simple` (8188fu §12) is GCC 6-only with no counterpart
there at all. Re-verify each mechanism against the 6.5.0 tree before relying on it.

---

## 1. `ez_new_sc_ioctl` — the strongest overlap

8188fu §21 reads, from `-fira-verbose=9`:

```
  pref0:a0(r124)<-hr1@2000      is_null
  pref1:a1(r116)<-hr1@2000      rq
  pref2:a1(r116)<-hr2@125       rq, because rq dies in `r2 = r116 + 16`
```

The sibling project hit this same decision, in this same pass, repeatedly. Four findings apply.

### 1.1 The `125` is structural, and the mechanism is named (adopt as background)

`ira-conflicts.c`'s `process_reg_shuffles`, reached from `add_insn_allocno_copies`: for any insn
with a `REG_DEAD` input and a different `OP_OUT` not bound by a matched-dup constraint, IRA
fabricates a copy at `freq < 8 ? 1 : freq/8`. At `-Os`, `REG_FREQ_FROM_BB` is the constant
`REG_FREQ_MAX` = 1000, so the weight is exactly `1000/8 = 125`. 8188fu observed the number; the
sibling project derived it. It is not a fluke and cannot be tuned.

The matching negative is already independently confirmed on 8188fu's side: **deleting the C-level
name does not remove the shuffle.** The sibling project proved it by inlining a ternary into its
use site and watching the identical shuffle re-form around an anonymous RTL temporary at the same
`freq=125`. 8188fu's sweep of five spellings of the third argument is the same result. Stop
respelling.

The only lever that works is changing *where* the dying operand's death actually falls: hoisting
the write to a point where the input has a genuine later reference elsewhere defers the death, and
the shuffle never forms.

### 1.2 The untried construct: a cross-jumped duplicate

**This is the single highest-value item in this document.** It manufactures the genuine later
reference §1.1 demands, and costs **zero bytes** in the final object.

```c
if (<some already-live boolean>) {
    if (<cond involving the loser>) <stmt>;
} else {
    if (<cond involving the loser>) <stmt>;   /* character-identical */
}
```

Why it emits nothing: `pass_jump2` runs *after* IRA and reload, in the `pass_postreload` group. It
cross-jumps the two identical arms into one block; `cleanup_cfg` then sees the outer conditional
with both edges landing on the same block and deletes it. **IRA, which ran first, has already
counted the duplicate.** The sibling project measured it at 90 → 68 differing bytes with the
section size and the instruction count both unchanged.

Preconditions, all measured there and all load-bearing:

| precondition | why it matters here |
|---|---|
| the duplicated body must itself end in a `GIMPLE_COND` | a bare straight-line statement is killed by `tree-ssa-tail-merge` before RTL ever sees two copies, and reproduces the original bytes exactly |
| free at the function tail; **not** free inside a block feeding a many-predecessor PHI join | the extra edge re-places that join's out-of-SSA copies. Check the instruction count, not just the byte count |
| the losing allocno needs a genuine competing preference | satisfied here: `a0` and `a1` both really want `hr1@2000`, and `a1` also wants `hr2@125`. This is a real tie, not an invented one |
| cannot constrain a *scheduling* tie | `pass_jump2` runs before `pass_sched2`. Irrelevant here — this is an IRA tie, decided earlier |

**Application.** The goal is that `rq` no longer carries `REG_DEAD` on the `add r2, rq, #16`, so
`pref2` never exists and the two `@2000`s decide the colour on their own. That needs a real
reference to `rq` *after* the address computation. `ez_new_sc_ioctl` ends in a sibcall, so the
duplicate has to sit between the address computation and the call, and each arm must contain a
genuine conditional that reads `rq`. 8188fu's §19 already establishes that cross-jumping fires in
GCC 6.5.0 on this very codebase — it is what keeps the earlier copy of the duplicated `ez_strsep`
and `ez_scan_device_ioctl_handle` tails — so the deletion half of the mechanism is already proven
on this target. What has *not* been tried is using it as an IRA reference-count device.

The sibling project also measured the device working **inside a loop** around one of two identical
conditional bodies, so "tail only" is a property of that one function's CFG rather than of the
device. The instruction count is still the thing to check.

### 1.3 Levers measured as *costly*, so budget them accordingly

Two other ways to reach the same tie, both verified there to reach the factory's register
assignment and both costing 4 bytes: (a) factor a reusable value out of one of the loser's own
call sites, so the loser has one fewer reference; (b) relocate the producing statement so the
shuffle never forms.

That conclusion transfers verbatim and matters a lot here, because every one of the 46 OEM
functions is pinned at the shipped address with the shipped size: **any** size growth in a function
whose downstream neighbours are pinned is an automatic, large net loss. A construct that wins the
tie-break honestly can still be strictly worse than not trying, so "does this reach the factory's
register assignment" is a necessary but **not** sufficient acceptance test — the standalone
object's byte count has to be checked first, before any splice.

### 1.4 Things this forecloses (adopt as closed, stop testing them)

- **`unlikely()` / `__builtin_expect` cannot move the tie — at all.** `REG_FREQ_FROM_BB` returns
  the constant `REG_FREQ_MAX` whenever `optimize_function_for_size_p`, which is unconditionally
  true at `-Os`. A reference inside a hot loop and a reference in a once-per-call failure tail
  therefore contribute identically to memory cost at this optimisation level. 8188fu §21 records
  this empirically as "does not move the block frequencies enough"; the correct statement is that
  it cannot move them at all, so moving a reference between blocks is not a lever that exists at
  `-Os`.
- **Neither `@2000` can be halved by removing a second reference — there isn't one.** `hr@2000` is
  `2×REG_FREQ_MAX` from two *by-design-redundant* credits to the **same single** collapsed
  hard-reg-move insn: one from `ira-costs.c`'s `process_bb_node_for_hard_reg_moves`, one from
  `ira-conflicts.c`'s `process_regs_for_copy` via `add_insn_allocno_copies`' `REG_DEAD` fast path.
  Not two call sites, not a block-frequency estimate. (The one guard that could suppress the second
  credit, `reg_class_size[rclass] <= ira_reg_class_max_nregs[rclass][mode]`, does not fire for a
  general-register class.)
- **A hard-register conflict never becomes a preference on a copy partner.**
  `update_costs_from_allocno` only ever writes a *partner's* cost table, gated by
  `!ALLOCNO_ASSIGNED_P`, so once an allocno pops it cannot be influenced retroactively; and a
  call-survival requirement is represented as a conflict, which has no channel to become a
  preference. Rules out "make the sibcall's ABI constraint pull `rq` the other way".
- **`__attribute__((optimize(...)))` cannot move an IRA cost tie.** A 28-option sweep there left the
  trace unchanged in every case. Two specifics worth knowing: `--param` is rejected outright by the
  attribute's parser, and `-fira-region=one` is *already* ambient at `-Os` (`toplev.c` hardcodes
  `flag_ira_region = IRA_REGION_ONE` when `optimize_size`), so naming it is a no-op rather than an
  untried lever.
- **`-fdbg-cnt` cannot oracle a register-allocation decision.** `grep -rn dbg_cnt` over `ira-*.c`,
  `lra*.c` and `reload*.c` returns zero hits; a counter can only gate a decision that calls
  `dbg_cnt`. The sibling project swept all 45 live counters against four allocation residuals; none
  moved. Do not spend a session on it.
- **The union / one-lane-vector round trip is *not* an IRA lever.** On an ordinary value it folds
  away before IRA and compiles bit-identically, verified there at four placements with
  `-fira-verbose=15`. It is a CFG/expression-differentiation tool only (see §2). Do not aim it at
  `ez_new_sc_ioctl`.

---

## 2. `ez_strsep` — `auto_inc_dec` / TER, and a site-local lever where 8188fu only has a global flag

The sibling project carried a translation-unit-local `-fno-auto-inc-dec` in one file for its whole
history for exactly 8188fu's reason: every natural `*p++` folded into a post-increment addressing
mode the factory does not use. They read `gcc/auto-inc-dec.c` and confirmed the same thing 8188fu
§18 confirmed — `get_next_ref` walks a per-basic-block memo table and refuses only when the add is
in a *different* `BLOCK_FOR_INSN`, never because it is textually far away — and then found a
**per-site** lever that retired the flag entirely:

```c
union { uintptr_t scalar;
        uintptr_t lane[1] __attribute__((vector_size(sizeof(uintptr_t)))); } v;
v.scalar = (uintptr_t)p;
p = (E *)(uintptr_t)(v.lane[0] + sizeof(E));
```

The mechanism: a vector-typed lane read is a different GIMPLE type from a plain pointer add, so
`tree-ssa-loop-ivopts.c` never offers it as an index-rewrite candidate; by RTL time the
bit-identical round trip is folded back to a plain add, but the intervening type change is enough
that `auto-inc-dec` no longer recognises it as a mergeable inc against the load.

**Why this is not something 8188fu already tried.** §18's ruled-out list includes "a cast through
`unsigned long`". A *scalar* round trip folds straight back out — measured there, twice — so that
failure is expected and is **not** evidence against the vector variant, which is a different GIMPLE
type and is the one measured as working.

**Why it is the right shape of lever.** 8188fu correctly rejected `-fno-auto-inc-dec` because it is
whole-TU and costs the loop's shipped `ldrb r3, [r5], #1`. The union round trip is applied to one
pointer bump, so it can deny the fusion at the `strb` site while leaving the loop's fusion intact.
That is precisely the property the residual needs and precisely what retired the flag there.

**Honest caveat, stated as a hypothesis and not a claim.** 8188fu's actual requirement is one level
earlier: TER must not sink `q + 1` past the NUL store. Denying only the *fusion* gives "right
order, wrong registers" (already measured with the flag). The reason the union form may also reach
TER — and the flag cannot — is that the union access carries virtual operands (`VUSE`/`VDEF`), and
`ssa_is_replaceable_p` / TER will not forward a statement with virtual operands across an
intervening memory store. That is a mechanism worth *testing*, not asserting. Test it by reading
`-fdump-rtl-expand` for whether insn 77 still lands after insn 76.

**A second lever from the same source that does *not* apply here, recorded so nobody tries it:** a
`struct __attribute__((may_alias)) { T word; }` wrapper stops `ifcvt` merging two arms that store
to the same address. `ez_strsep` *wants* the merge — it needs cross-jumping to keep the earlier
`str r3, [r7]` — so this one is backwards for this residual.

---

## 3. `process_config_vars` — out-of-SSA / coalescing, and the "wrong skeleton" test

### 3.1 The closest mechanism analogue

**Clean negative first: `uncprop` (`tree-ssa-uncprop.c`) appears nowhere in the sibling project's
notes.** There is no precedent there for that specific pass.

What there *is* is the adjacent family, worked in detail. One of their residuals was a `mov`
landing at the end of a loop preheader instead of at its written position, because a pointer copy
was copy-propagated away, leaving `tree-outof-ssa` no GIMPLE statement position to hang the
resolving PHI copy on — so it appended the copy at the end of the block. The lever that closed it:
a pointer-to-pointer copy is eligible for GCC's SSA copy-coalescing regardless of pointee type
(confirmed across `char *`, `void *`, `u16 *` and `const u8 *` — all coalesce away identically),
whereas a pointer-to-**integer** conversion is not, so the statement survives as a real, positioned
GIMPLE statement. Measured 21 → 14 differing bytes.

Two details worth copying: they first tried five pointer-typed spellings and a full
pointer→integer→pointer round trip, all byte-identical to the baseline (the round trip folds back
to the same type); and the winning declaration had to be **first** in the block — second or last
lost the win.

**Application.** `process_config_vars`'s blocker is that `uncprop` rewrites all seven main-path
`pos = 0` PHI arguments into the guard temp, so out-of-SSA's per-edge coalesce costs put the temp
in `pos`'s partition. The transferable idea is *type-class differentiation to make a value
ineligible for coalescing*, and their measurement says the pointer/integer boundary is the
strongest such boundary available in ordinary C. 8188fu §15 already found the weaker form of the
same thing (a named typedef of `int` is a distinct type to `uncprop`; `int n` and `s32 n` compile
differently), so the family is known to bite on this target; only the strongest member of it is
untried.

**Prior worth having before spending a session on flags:** the same source records a long list of
flags measured completely inert on that residual — `-fno-tree-coalesce-vars`, `-fno-tree-ter`,
`-fno-tree-fre`, `-fno-tree-pre`, `-fno-tree-ch`, `-fno-move-loop-invariants`, `-fno-ivopts`,
`-fno-tree-sink`, `-fno-caller-saves`, `-fno-tree-vrp`, `-fno-tree-copy-prop`, `-fno-tree-dce`,
`-fno-tree-loop-optimize`, `-fno-tree-slsr`, `-fno-tree-forwprop`, `-fno-tree-ccp` — no effect at
all. Do not expect a flag to move a coalescing residual.

### 3.2 The "wrong skeleton" test — the highest-value process item for this function

The profile fits `process_config_vars` uncomfortably well: a function patched across many rounds,
where each round's diagnosis is a plausible allocator phenomenon that the next round's fix does not
quite reach.

The rule: stop patching and re-derive. Read the factory disassembly cold, write the control-flow
graph and every value's live range from that reading alone, write the C from *that*, then diff the
fresh derivation against the standing source. Where they differ is a hypothesis with a reason
attached; where the fresh derivation is simpler, prefer it.

Their worked example is directly instructive. Four-plus sessions of `-fira-verbose=15` archaeology
on one function dissolved in minutes once the function was re-derived cold. The actual cause was
structural, not allocator: a working pointer was computed as *base + byte_offset* — the right
value, taken from a raw parameter — where the factory computes it as *base + (index << 2)*. Same
value, but **dependent on the index**, and that dependency is what keys the index's register choice
to the same decision that places the pointer. 124 → 0 differing bytes. That is exactly the shape of
"a register cascade is a symptom of a missing data dependency", and it is the shape
`process_config_vars` presents: 44 of 86 words differ but the register-blanked edit distance is
only 5.

The cheap pre-check that goes with it: compute the plain byte-match percentage first. Above ~80%,
expect a fresh derivation to *reconverge* on the standing source, so budget it as a confirmation
pass; below that, expect it to diverge and treat the rewrite as worthwhile. `process_config_vars`
is 265/344 = **77.0%** — just under the line, i.e. the one function of the three where a cold
re-derivation is indicated. (`ez_new_sc_ioctl` at 17/56 differing is 69.6% but is only 5 words of
14 and has a fully named single cause, so the percentage is misleading there; `ez_strsep` at 6/156
is 96%.)

---

## 4. Instrumentation — the biggest tooling gap, and 8188fu is already 90% of the way there

The sibling project built `cc1` from the pinned release source and added getenv-gated hooks, all
inert when unset. Because 8188fu **already builds GCC 6.5.0 from source** (`FINDINGS-toolchain.md`,
for `--with-pkgversion`), the marginal cost of this is small — the tree, the prerequisites and the
build recipe already exist and are proven.

| hook | what it converts into a bound |
|---|---|
| `IRA_FORCE_HR` | override the chosen hard register for a named pseudo (`assign_hard_reg`) |
| `IRA_FREQ_DEBUG` | annotate every `Pushing` line with `[freq=, thread=, head=]` |
| `IRA_BUMP_FREQ` | perturb `ALLOCNO_FREQ` in `init_allocno_threads` **without touching the graph** |
| `IRA_NO_THREAD` | refuse a named copy's merge in `form_threads_from_copies` |
| `IRA_COLOR_DEBUG` | log both sides of the colorability decision per allocno |
| `IRA_FORCE_COLORABLE`, `IRA_AVAIL_DELTA`, `IRA_CSIZE_DELTA`, `IRA_RESORT` | perturb each input of the colorability decision independently |
| `IRA_PROFIT_DEBUG` | log `setup_profitable_hard_regs`' cost filter, per register |
| `IRA_CALLFREQ_DEBUG` / `IRA_CALLFREQ_DELTA` | print and perturb `ALLOCNO_CALL_FREQ` |

**What it buys, concretely.** Before hunting a single C spelling, one compile per lever produces a
table of *which levers reach a byte match at all, and where they overshoot*. In their worked case
one lever turned out to be by far the widest target — a factor of ten between the smallest and the
largest perturbation that still worked — which is why a single round sufficed; the other levers
were never spellable in ordinary C at all, and were recorded so that a future round on a similar
residual would have them. 8188fu ran roughly **70,000 generated variants** for these three
functions. A hook table would bound that search first: for `ez_new_sc_ioctl`, `IRA_NO_THREAD` or
`IRA_FORCE_HR` answers "does flipping `rq`↔`is_null` even produce the shipped bytes?" in one
compile — and if it does not, the whole spelling search is misdirected and the residual is not
solely this tie. That is exactly what they found for three of their four residuals.

**Three disciplines to copy exactly:**

- The hooked compiler is **diagnosis only**. Every acceptance measurement comes from the unmodified
  installed compiler, and a `--verify-only` run re-proves that the hooked build reproduces the
  stock build byte for byte with no variable set.
- **The regno-collision trap.** Pseudo regnos restart per *function* within a translation unit, so
  an env-var setting keyed on a regno can silently perturb an unrelated function that happens to
  share it. They regressed a previously byte-exact function this way. `ez_wifi_config.c` holds many
  functions, so always re-score **all 46** after a forced compile, not just the target.
- Verify a found GCC source tree for pre-existing `getenv` hooks before patching it — a tree that
  matches `BASE-VER`/`REVISION` can still carry another session's instrumentation, and the tell is
  the patch tool's hunk-reject count.

---

## 5. Comparison-harness traps — two classes, 8188fu has one of them

### 5.1 The unowned-byte class

The sibling project carried two wrong bytes for its entire history at an address **outside every
labelled function's extent**, so no per-function verdict row could ever report them. The root cause
was a `struct` without `packed` whose `sizeof` rounded 50 up to 52, zero-filling into erase pad.
The fixes worth copying are the *tooling* ones:

- an unconditional, **never-truncated** "differing bytes outside all function extents" section in
  the verifier (their previous print cap was part of why it hid);
- a full byte-ownership audit over the whole image as a standing, unconditional last stage of the
  verification target;
- and the confirmation discipline: **they reverted only the source fix, kept the new check, and
  rebuilt to prove the check actually fires.**

8188fu has the analogous scar already (§20: four functions byte-identical in content but in the
wrong `.text` position, passing every per-function check while costing 1,280 bytes, invisible
because `oemdiff.py` compares symbolically). The addition is to make the unowned/unattributed line
unconditional and never truncated, and to test the check by reverting a known fix.

### 5.2 The exempted-field class

27 function addresses were wrong in their ledger for a long time because the pointer words were
FLOAT-exempt in one checker while the other checker only tested byte *completeness* — it gap-filled
sizes, so wrong addresses still produced "0 uncovered". The rule: **a field exempted from
verification by every checker is unverified everywhere.**

8188fu already has one documented instance (`PLAN.md`: `fulldiff.py` strips `.NNNN` uniquifiers
before comparing `.strtab`, so a `.strtab` scored 0 is not necessarily byte-identical — hence
`uidgap.py`). The transferable action is to *enumerate* every masked or exempted field across
`fulldiff.py`, `offsetdiff.py`, `oemdiff.py`, `align.py` and `lab.py`, and confirm each one is
covered by at least one other check. The known maskings are: structural-count size-delta charging,
symbolic relocation and branch-displacement masking, `.NNNN` stripping, and register-blanking in
the `s` score.

### 5.3 Alignment accounting must close

Align the two instruction streams with `difflib.SequenceMatcher` (a naive `diff -y` mis-aligns
after the first divergence and hides the true insert/delete points), then **sum each opcode's
actual byte length, not its instruction count** — narrow and wide encodings differ even where the
mnemonic LCS calls two instructions "equal". The running total must close to *exactly* the known
size gap with nothing left over; if it does not, the alignment missed something and the accounting
is not finished. 8188fu's `align.py` already does the alignment; the addition is the closure check
as an invariant, which is what turned a vague hypothesis into a refutation-plus-true-cause there.

---

## 6. Honest negatives — where the overlap is thin or absent

- **Toolchain identification: nothing to adopt.** Their method — score one translation unit across
  six installed releases and look for a function that closes under exactly one — is *weaker*
  evidence than what 8188fu already holds: a rebuilt compiler whose `.comment` reproduces the
  shipped string verbatim, plus 158/158 objects byte-identical to stock modulo `.comment`. They
  tested and rejected the "vendor IDE ships a different build of the same compiler" hypothesis;
  8188fu has already settled the same question more directly.
- **`.note.gnu.build-id`, ELF notes, `.modinfo`, module ELF layout: nothing at all.** That project
  targets a bare-metal flat image with a hand-written footer, not an ELF relocatable. And the 19
  build-id bytes are derivative anyway — an SHA-1 over the linked output — so they close
  automatically when the other 102 do. Not a work item.
- **Reproducible-build infrastructure (`SOURCE_DATE_EPOCH` and friends): nothing.** Their notes only
  record where the `__DATE__`/`__TIME__` stamp lands in the image. 8188fu already solved the build
  path and timestamp problem (`FINDINGS-byte-gap.md` §3).
- **`-Os` block layout: no counterpart.** 8188fu's §12 — `reorder_basic_blocks_simple` skips its
  edge sort when optimising for size, so branch probabilities are computed and then ignored — is a
  GCC 6 fact. They are on 4.9/5.4 and have nothing equivalent; their older observation ("which arm
  is written as the `if`-body") is the weaker form of the same territory.
- **Decompiler-output reconstruction: methodologically similar, technically not transferable.**
  Their methodology notes include a large catalogue of Hex-Rays `goto`-unwinding idioms and which
  of them do and do not reproduce a given block layout. But it is a Thumb-2 / GCC-4.9 catalogue,
  and 8188fu's §19 ("a shared tail is duplicated source; a `goto` in a reconstruction is a
  hypothesis, not an observation") is the same insight independently derived and *better stated*
  for this target. Worth reading for idiom candidates, not for rules.

---

## 7. Documentation conventions worth adopting (cheap, and they change behaviour)

Their filing rule, which is worth copying because it changes what gets written down:

- a source-shape rule that generalises goes in the numbered rule list;
- something measured about the compiler goes in the compiler-fingerprint document, **with the byte
  counts**;
- something asserted without proof goes in the open-questions document.

A finding with no byte count attached is an opinion. Do not write it down as if it were a result.

And the maxim that runs through the whole corpus: a claim of the form *"no source shape can reach
this"* is only as good as the mechanism it names.

Two process observations they record about themselves, which apply directly to a residual this
narrow:

- **The recognisable failure shape.** When consecutive rounds each add a term to an impossibility
  argument rather than attacking a different decision, the argument is growing because the axis is
  fixed.
- **Exhaustive build-space sweeps are a closure argument, not a search.** In one such sweep, 5,006
  configurations produced exactly one informative result: 284 of 291 per-function tree/IPA pass
  toggles printed the *identical* object — i.e. the whole GIMPLE pipeline is inert on an RTL
  residue — and 1,170 of 1,296 configurations printed one byte-identical object, proving that the
  register choice is not a build parameter. That is the right way to retire a flag hypothesis
  permanently, and it is a much stronger statement than "we tried some flags".
