# Case study — reproducing a vendor's `8188fu.ko` byte for byte, and the oracles that got there

> **What this is.** An account of the reproduction of a Realtek `8188fu.ko` Linux kernel module
> pulled from a Hikvision IP camera, from a public driver tarball and nothing else — no vendor
> source, no vendor toolchain, no kernel `.config`, no build log. The rebuilt module is
> byte-identical to the shipped one — all 1,918,056 bytes, `cmp` silent, from a clean
> `git archive` of HEAD. This document is about the parts a reader could not easily have worked
> out themselves — the oracles that convert a stripped binary into exact numeric constraints on a
> build configuration, the counting arguments that bound what is missing, the `-Os` codegen rules
> the work had to derive, the compiler decisions the last three functions came down to, and
> the traps that made two harnesses report success over real errors.
>
> Byte-exactness is a statement about the *object code*. The source that produces it is not the
> vendor's text and cannot be shown to be, and several constructs in it were chosen for the
> compiler rather than for a reader; §12 says which, and what the binary is still silent about.
>
> Per-barrier detail lives in `FINDINGS-hardware.md`, `FINDINGS-vendor-kernel.md`,
> `FINDINGS-driver-config.md`, `FINDINGS-byte-gap.md`, `FINDINGS-toolchain.md` and
> `FINDINGS-oem-catalogue.md`; this document does not repeat their tables and cites them by section.
> Where the two disagree, the FINDINGS docs are authoritative and the disagreement is flagged here.

---

## 1. The result

```
whole file        1,918,056 bytes;  0 differ.  `cmp` is silent
                  a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13, both files
sections          41 of 41 byte-identical
symbols           3,909 FUNC symbols, every one at the shipped address with the shipped size
.strtab           byte-identical, 124,098 bytes, 879/879 DECL_UID uniquifiers matched
```

```
compiler   arm-linux-gnueabi-gcc 6.5.0, rebuilt from the FSF release tarball with
           --with-pkgversion='arm_multilib_uclibc_20200924'; -Os, soft-float,
           -march=armv7-a, the vendor kernel's own Kbuild flags
kernel     Linux 4.9.129 + Fullhan vendor patch, fh8856v200_defconfig,
           one edit: ARCH_FH885xV200's `select CPU_V6` -> `select CPU_V7`
source     the public rtl8188fu tarball, plus two OEM translation units
           (46 functions, ~9.6 KB of .text) reconstructed from Hex-Rays output
```

`build/verify.sh` reproduces that from a clean `git archive` of HEAD, builds the export twice to
show that nothing in the build is non-deterministic, and asserts the hash; CI runs the same script
on every push. A `cmp` of two 1,918,056-byte files cannot be fooled by a masking rule, which makes
it a different kind of claim from every scoreboard number below it (§8).

The last four to close, and the decision each came down to:

| | bytes | the deciding pass | what closed it |
|---|---:|---|---|
| `process_config_vars` | 79 | `tree-ssa-dom` on the `m` cstore; `uncprop` and out-of-SSA coalescing on the `pos` tail; IRA's colouring order on three registers | a `_Bool` flag with an explicit `& 1`, one shared `pos = 0` behind a barrier that uses it, and three reference devices |
| `ez_new_sc_ioctl` | 17 | one `assign_hard_reg` tie decided by a weight-125 shuffle copy — and, before it, by IRA's colouring order | two empty `asm`s, which are two more RTL references to `is_null` |
| `ez_strsep` | 6 | TER sinking `q + 1`, then `auto_inc_dec` fusing it into a post-increment | a store TER will not move an expression across |
| `.note.gnu.build-id` | 19 | an SHA-1 over the linked output | the other 102 bytes |

The build-id was always derivative: it closed by itself when the rest did, and was never
independent work. All three functions were the **right size** and at the **right address** long
before they were right — the edit distance the search was steered by is the register-blanked
instruction distance — so what was left at the end was a register-allocation and
statement-placement problem, not a structural one. §10 is each of the three in full.

The arc, from the commit log (72 commits to `BYTE-EXACT: 8188fu.ko reproduces bit for bit`):
37,630 → 28,368 (vendor `pkgversion`) → 1,296 → 972 → 455 → 348 → 96 → 56 bytes of OEM `.text`,
then a whole-file recount that exposed 1,421 (§8 below), → 141 → 126 → 121 → 116 → 99 → 65 → 57
→ **0**.

---

## 2. Struct sizes are a config oracle, and a `.ko` publishes three of them for free

The single most reusable finding here. A stripped kernel module does not contain its `.config`,
but it does contain *exact integers* that a `.config` determines, and three of them are readable
without any disassembly at all.

**`sizeof(struct module)` is the size of the `__this_module` symbol.** Every module defines
`__this_module` as a `struct module`, so `readelf -sW` prints the number directly. The shipped
module says **384**.

**`ALIGN(sizeof(struct net_device), 32)` is the `netdev_priv()` offset**, and it is baked into
every `ldr`/`str` immediate that touches driver-private data. The shipped module says **992**;
`proc_get_ldpc_cap` opens with `ldr r3,[r0,#72]` / `ldr r3,[r3,#992]` and says so in two
instructions.

**`sizeof(struct iw_handler_def)` is the size of `rtw_handlers_def`** — 24, which is the size
*with* `CONFIG_WEXT_PRIV`, so the vendor shipped a WEXT-capable kernel. That was read off the
symbol table before any Kconfig was examined, and it is why the wireless-extensions question was
settled by evidence rather than by assumption.

Three scalars is enough to discriminate between kernel builds decisively. `build/probe/` compiles
one global per kernel struct, sized by `sizeof()`, so the ELF symbol sizes in `probe.ko` read out
the struct layout of whatever kernel is prepared:

| | target | stock 4.9.129 + fragment | vendor BSP as shipped | **vendor BSP + `CPU_V7`** |
|---|---:|---:|---:|---:|
| `sizeof(struct module)` | 384 | 384 | 352 | **384** |
| `netdev_priv()` offset | 992 | 1120 | 992 | **992** |
| `sizeof(struct iw_handler_def)` | 24 | 24 | 24 | **24** |

**The lesson is in the second column, not the fourth.** The hand-built stock kernel also reaches
384 — by disabling nine options (`KALLSYMS`, `JUMP_LABEL`, `FTRACE`, …) in a reconstructed
fragment. The vendor config reaches 384 with `CONFIG_KALLSYMS=y` and `CONFIG_JUMP_LABEL=y` still
on, purely because `ARM_L1_CACHE_SHIFT_6` is `default y if CPU_V7`, which makes
`____cacheline_aligned` 64 bytes wide. **A single scalar constraint has many solutions, and the
reconstructed fragment was fitting the right number for the wrong reason.** The confirmation is the
structs the probe was *not* being scored on, which moved just as decisively — `struct device`
336 → 216, `struct dev_pm_info` 120 → 20, `struct usb_device` 728 → 600, `struct wiphy` 640 → 512.

The `CPU_V6` → `CPU_V7` retarget is worth stating plainly because the BSP is *wrong for the
hardware in hand*: the only board entry in the drop hardcodes `select CPU_V6`, all twelve
"defconfigs" therefore stamp `vermagic` as `ARMv6`, and the camera is an FH865x (Cortex-A7) whose
module says `ARMv7`. The FH865x board entry lives in a sibling BSP drop that was never obtained.
Flipping the one `select` gives `-march=armv7-a`, the exact `vermagic` string, and the 64-byte
cache line that explains `sizeof(struct module)` — three consequences from one line.

Measured effect of switching kernels alone, with every driver flag held fixed: semantic identity
2197/3939 (55.8%) → **2570/3939 (65.2%)**, `.text` from +3.04% oversized to −0.31%.

### 2.1 The same oracle one level down: a driver struct

`sizeof(struct mlme_priv)` is not a symbol, but it is recoverable from the offset histogram (§4)
and it came out **4168** against the reconstruction's 2856. Sweeping candidate `#ifdef`s through a
size probe identified `CONFIG_APPEND_VENDOR_IE_ENABLE` as the flag that produces exactly 4168 — the
members are `vendor_ie_mask[5]`, `vendor_ie[5][255]`, `vendor_ielen[5]`, and the growth is **+1312
to the byte**, not approximately. (`5*255 = 1275`, plus `2*20` and alignment to the struct's
8-byte `__alignof__` — the "why 1312 and not 1316" arithmetic is `FINDINGS-driver-config.md` §1.)

That one flag accounted for more than 98% of the remaining struct-layout corrections in the
histogram. It was independently corroborated from the symbol table, which carries seven
`rtw_vendor_ie_*` / `rtw_build_vendor_ie` symbols the reconstruction did not have — the same flag,
found twice by unrelated routes.

---

## 3. The symbol table is a configuration fingerprint

Two distinct arguments, both cheap, both usable before a single instruction is compared.

**`depends=` being empty proves built-in, not merely present.** `.modinfo`'s `depends=` field lists
only modules whose *exported* symbols this module references. The shipped `depends=` is empty, and
the module plainly references `cfg80211_*`, `register_inet6addr_notifier` and `usb_*`. Therefore
`CONFIG_CFG80211=y`, `CONFIG_IPV6=y` and `CONFIG_USB=y` — built into the kernel image, not `=m`.
That is a three-option conclusion from an empty string.

**Which out-of-line helper a piece of inline code calls names the config that generated it.** The
useful ones are the pairs where two spellings of the same operation differ only by a config:

| observation | conclusion |
|---|---|
| no `_raw_spin_lock*`, no `_raw_read_lock*` | `CONFIG_SMP=n`, `CONFIG_DEBUG_SPINLOCK=n` → `spinlock_t` is **0 bytes** |
| `kmem_cache_alloc` present, `kmem_cache_alloc_trace` **absent** | `CONFIG_TRACING=n` |
| no `__gnu_mcount_nc` | no ftrace |
| no `__stack_chk_fail` | no stack protector |
| no `preempt_count_add`/`_sub` | `CONFIG_PREEMPT_COUNT=n` → `CONFIG_PREEMPT=n` |
| no `_cond_resched` | `CONFIG_PREEMPT_NONE=y` rather than `PREEMPT_VOLUNTARY` |

`kmem_cache_alloc` vs `kmem_cache_alloc_trace` is the sharpest of these: same call site, same
source line, and the choice between the two symbols is made entirely by whether tracing is
compiled in. The `spinlock_t`-is-zero-bytes conclusion then propagates into every struct layout in
the driver, which is why it is worth extracting before anything else.

### 3.1 Absent code is evidence, and `.rodata` strings make it a proof

Forty of the fifty-two functions built-but-not-shipped were one family (`LPS_*`, `ips_*`,
`rtw_set_ps_mode`, …), i.e. `CONFIG_POWER_SAVING`. What turns that from a plausible reading into a
proof is that `core/rtw_pwrctrl.c` mixes guarded and unguarded code in one file, so its strings
split cleanly:

| string | enclosing guard | in shipped? |
|---|---|---|
| `%s: Driver Already Leave LPS` | *(top level)* | yes |
| `%s: IPS_mode=%d, LPS_mode=%d, LPS_level=%d` | *(top level)* | yes |
| `==>ips_enter cnts:%d` | `#ifdef CONFIG_IPS` | **no** |
| `It can't execute LPS without Wi-Fi connection!` | `#ifdef CONFIG_LPS` | **no** |
| `change DTIM from %d to %d, ...` | `#ifdef CONFIG_LPS` | **no** |

Every unguarded string survives and every guarded one is absent. **The split being perfect is what
makes it a proof rather than a guess** — one guarded string present would have refuted the whole
reading. Two derivation traps had to be checked first, since both silently re-enable `CONFIG_LPS`
behind `CONFIG_POWER_SAVING=n`: `autoconf.h`'s `#ifdef CONFIG_BT_COEXIST → #define CONFIG_LPS`
(harmless, BT_COEXIST is off) and `drv_conf.h`'s `#ifdef DBG_CONFIG_ERROR_RESET → #define
CONFIG_IPS` (harmless, that symbol sits inside a block comment). Verified afterwards with
`gcc -dM -E` rather than by reading the headers.

**A by-product worth keeping: GCC's clone counters are a translation-unit-order oracle.** Twelve of
the fifty-two ours-only functions were `*.constprop.N` suffix collisions. After the rebuild every
`constprop`/`part` suffix number matches the shipped module exactly — and those counters only line
up if the same functions were compiled in the same order from the same set of translation units.

---

## 4. The offset-differential method, and the trap that makes one fact look like thirteen

`build/offsetdiff.py` disassembles both modules, pairs same-size functions, and reads
`(our offset → their offset)` out of matched load/store and add immediates. A struct-layout error
is then a *scalar*: a histogram of deltas with a site count.

This localises a layout bug to one number in one struct, which is far stronger than a byte diff.
`_rtw_read16` isolates the `mlme_priv` growth in five instructions.

**The trap.** ARM cannot encode a large offset in one `imm12`, so GCC splits it into
`add rX, rY, #<high>` plus a second `add`/`ldr` immediate, and the differ scores the halves
separately. The aggregated histogram over the top 400 pairs looked like thirteen distinct problems:

```
 -2784 × 1054      +4096 ×  714      +1312 ×  612      -32 × 195      +32 × 182
 +1344 ×  169      +1280 ×  168      +1216 ×   28      +160 ×  22     +1152 × 21
   +96 ×   73       +48 ×    6      +1264 ×    5
```

Every pair recombines to the same number:

```
+4096 + (-2784) = +1312    +1344 + (-32) = +1312    +1280 + (+32) = +1312
+1216 + (+96)   = +1312    +1152 + (+160) = +1312   +1264 + (+48) = +1312
```

**Thirteen histogram rows, one fact.** Read a differential histogram for split-immediate pairs
before treating its rows as independent, or a single struct will be reported as a dozen unrelated
regressions.

**A second discrimination step, on the other side of the same instrument.** When the differing
words are `ldr`s through a literal-pool base pointer, a ±4 shift is only real layout if the two
pool words carry the *same* addend. In `loadparam` both carried `.data+1576` and `.bss+21872` in
both modules, so the bases were identical and the shifts were genuine — which led straight to
`rtw_tx_pwr_lmt_enable` sitting in `.data` in the shipped module and in `.bss` in the
reconstruction. A zero initialiser puts it in `.bss`, a non-zero one in `.data`; reading the
shipped `.data` at that offset gives the value directly, **1**, i.e. `CONFIG_TXPWR_LIMIT_EN=y`.
Everything after it in each section had been sliding by four.

> The brief that prompted this document described the trap as "PC-relative literal-pool loads
> masquerading as struct offsets". That is not what the docs record. The literal-pool interaction
> is the *discriminator* above — check the pool addend before believing a ±4 — and the trap proper
> is the split-immediate recombination. Corrected here.

---

## 5. Counting copies: four oracles that bound what is missing without identifying it

The most transferable idea in the whole project. Several artefacts in an ELF are emitted **once per
something**, so counting them measures a quantity the binary otherwise conceals.

**`.comment` counts translation units.** GCC emits its `.ident` string once per TU; the linker
concatenates them without deduplication. The shipped module carries
`GCC: (arm_multilib_uclibc_20200924) 6.5.0` **159** times; the reconstruction carried
`GCC: (GNU) 6.5.0` **157** times. Two facts fall out at once: the pkgversion string (§6), and that
**exactly two translation units were missing** — not "some OEM code", but two files. That was
cross-confirmed independently by the `STT_FILE` symbols, and independently again by
`FINDINGS-byte-gap.md`'s separate deduction. Three routes, one number.

**`__func__.NNNN` uniquifiers are `DECL_UID`s.** When two `__func__` string literals would collide,
GCC appends the declaration's `DECL_UID`. Those numbers are a monotonic count of *every*
declaration the front end has created so far in the translation unit — so the gap between two
consecutive uniquified symbols is an exact count of declarations between them, including
declarations that emit no code at all. The accounting was measured against this exact compiler:

| construct | DECL_UIDs |
|---|---:|
| function definition, before its body | `nparams + 2` (PARM_DECLs, then FUNCTION_DECL, then RESULT_DECL) |
| `(void)` parameter list | counts as one parameter; `()` counts as none |
| `struct`/`union` definition | `nfields + 1` |
| `enum` definition | `nvalues + 1` |
| prototype | `1 + max(nparams, 1)` |
| `for` / `while` loop | 3 — artificial labels, created where the loop *ends* |
| a definition that follows a prototype | +1 for the merged-away duplicate |

`__func__` is created at its **first use** inside a function, not at the function's start, so a
late `__func__` counts everything declared before it.

This turns into an oracle for **header structure and source order**, which is otherwise
unrecoverable. The vendor's OEM header carried types and extern objects but *not* prototypes;
splitting `include/ez_wifi.h` into `ez_wifi.h` + `ez_wifi_fn.h` took the mismatch from **726
symbols to 16**. A third source-order fix and one dropped local closed the two intervals that were
*over*. Final state: **879 of 879**, `.strtab` byte-identical. Delete any one placeholder and every
`__func__.NNNN` after it in that file stops matching.

**`__LINE__` constants bound an unavailable patch.** Three public files carry `__LINE__` values
that pin how many lines the vendor inserted above a given point:

| file | function | shipped `__LINE__` | delta |
|---|---|---:|---:|
| `core/rtw_mlme_ext.c` | `collect_bss_info` | 10582 | +60 |
| `os_dep/linux/ioctl_linux.c` | `rtw_wx_set_priv` | 7840 | +2 |
| `core/efuse/rtw_efuse.c` | `rtw_efuse_map_write` | 2876 | +1 |

The recovered `OnProbeReq`/`OnProbeRsp` code accounts for 21 of the 60, and all three functions now
compile byte-identically, so the *code* above `collect_bss_info` is fully accounted for. The other
39 lines emitted nothing — comments, blank lines, a different wrapping style — and the binary
cannot say which.

**And one of those single lines turned out to be a brace.** `rtw_efuse.c`'s `+1` was initially
filed as a register-allocation difference around a `printk` (`FINDINGS-byte-gap.md` §4.2). It is a
semantic fix. Realtek's own source has a brace bug in the efuse map dump:

```c
	for (i = 0; i < mapLen; i++) {
		if (i % 16 == 0)
			RTW_PRINT_SEL(RTW_DBGDUMP, "0x%03x: ", i);
			_RTW_PRINT_SEL(RTW_DBGDUMP, "%02X%s", ...);
		}
```

so the second print runs every iteration. The shipped module's control flow says the vendor's copy
does not: at `rtw_efuse_analyze+0x974` it branches on `i % 16 != 0` straight to the loop increment,
past **both** prints, where the reconstruction branched past only the first. Adding the braces
reproduces that — and with the second print inside the `if`, GCC has the registers to keep both
separator strings live across the loop instead of reloading one from the pool, which is exactly the
six-instruction window that differed. **Closing the brace costs exactly one line, which is the `+1`
the two `__LINE__` constants demanded.** A codegen residual, a line-count constraint and an
upstream bug fix, all one edit.

---

## 6. `.comment` names the compiler exactly, and `--with-pkgversion` is why

`gcc/toplev.c` in the 6.5.0 release:

```c
      const char *pkg_version = "(GNU) ";
      if (strcmp ("(GCC) ", pkgversion_string))
	pkg_version = pkgversion_string;
      ident_str = ACONCAT (("GCC: ", pkg_version, version_string, NULL));
```

`pkgversion_string` is `PKGVERSION`, which `configure` sets to `"($withval) "` from
`--with-pkgversion=` and to `"(GCC) "` when absent — hence the `"(GNU) "` fallback above, and hence
a stock compiler's `.comment` disagreeing with its own `--version` banner. Nothing else reads
`pkgversion_string` on a compile path: it reaches `.comment` and the `--version`/`-v` banners, and
that is the whole list.

So `GCC: (arm_multilib_uclibc_20200924) 6.5.0` is a configure-time string with **no codegen
meaning**, and the same string appears in a sibling camera's kernel banner as
`gcc version 6.5.0 (arm_multilib_uclibc_20200924)` — the banner prints `version_string` then
`pkgversion_string`, the ident prints them the other way round, and there is no other reading of it.

Rebuilding GCC 6.5.0 from the FSF tarball with that one configure option (and no patches — "none.
Not one") produced a compiler whose `.comment` reproduces the shipped string verbatim and whose
**158 object files are byte-identical to the stock compiler's once `.comment` is removed**. That is
the useful form of the result: it proves the vendor string is cosmetic *and* removes 9,347 bytes of
difference. The alternative — inferring the compiler by scoring several installed releases and
looking for one that uniquely closes a function — was never needed here, because the ident string
named it outright.

---

## 7. What GCC 6.5.0 at `-Os` had to be taught

Rules derived along the way, each worth multiple functions. These are the ones that read *backwards*
from a binary to a source shape.

**Block layout at `-Os` is source order, not profile.** GCC 6's `reorder_basic_blocks_simple` skips
its edge sort entirely when optimising for size, so branch probabilities — including the very
strong `PRED_COLD_FUNCTION` the kernel's `__cold` `printk` puts on every error path — are computed
and then ignored. Blocks are chained in GIMPLE order.

**Therefore a shared tail is evidence of *duplicated source*, not of a `goto`.** This is the
corollary, and it closed the two largest remaining residuals. If a block is reached from two places,
the source could have produced it either by a `goto` to a common label or by two copies that
cross-jumping merged — and **both routes produce the same final layout**. What differs is the
expression graph that reaches the register allocator, because each duplicated copy is CSE'd,
propagated and scheduled in its own basic block *before* the merge happens.

`ez_scan_device_ioctl_handle` had been written with `goto trig_scan`. The vendor wrote the tail
twice. With the whole body duplicated into both arms, the function is byte-identical, pool included.
The mechanism is precise: `probe_req_t.id` is an unaligned `u16` in a packed struct, so GCC builds
`&probe_req_t` explicitly to address the two byte stores, and the memcpy destination builds it
again. With the `goto`, the two live in different basic blocks, nothing combines them, and
`cse_local` folds the second into the single constant `.LANCHOR0+622` — which must go in the
literal pool, because 622 is not an encodable ARM immediate. Duplicated, the two are in the same
block and survive as `add r5, r4, #612` / `add r0, r5, #10`. **That one pool word was displacing
eleven relocations**: `.rel.text` went 280 → 32 bytes and the whole file 348 → 96.

> **The practical rule: a `goto` in a reconstruction is a hypothesis, not an observation.**

**A named typedef of `int` is a distinct type to `uncprop`.** `uncprop` rewrites *constants* in PHI
arguments into SSA names already known to hold that constant. For a `switch` it records
`index == case_value` on every single-valued case edge — but only if the types match.
`ez_set_new_sc` was 12 bytes short because `ret` (an `int`) could not be rewritten into a `u32`
switch index. With `int sc_cmd[2]` the rewrite fires, `ret` coalesces with the selector, case 0
needs no `ret = 0` at all because it already left 0 in `r4`, and the epilogue is the shipped
`mov r0, r4`.

**`||` reverses its operands; `&&` does not.** `if (!dev || !rq)` emits `cmp rq; cmpne dev`. So
which order the vendor wrote is readable off the binary — and it is not consistent between
functions, which is itself worth knowing before "normalising" a reconstruction.

**Error paths land out of line only when they are the `else`.** A guard-clause early return puts
the error block in the fall-through; `if (good) { work } else { log; return; }` puts it after —
which is what the shipped module has everywhere.

**GCC 6.5 refuses to fold `strcpy` at `-Os`** (`gimple_fold_builtin_strcpy` bails unless the length
is zero when `optimize_size`), so inline copies must be written as `memcpy`. And
`char version[32] = {0};` is a `memset` call while `memset(v,0,32)` is `__memzero` — ARM's
`asm/string.h` macro rewrites the latter, and an initialiser never goes through the macro.

**VRP's `register_edge_assert_for` recurses into an `IOR` only for `== 0`.** In GCC 6, for
`if (X != 0)` on the edge where `X == 0`, it recurses into `X`'s defining `BIT_IOR_EXPR` and
asserts *both* operands zero:

```c
  if (((comp_code == EQ_EXPR && integer_zerop (val))
       || (comp_code == NE_EXPR && integer_onep (val))))
    { ... register_edge_assert_for_1 (op0, EQ_EXPR, e, si);
          register_edge_assert_for_1 (op1, EQ_EXPR, e, si); }
```

so a plain `if (pos | n)` proves `n == 0` on the whole main path and kills `n` across two calls.
The recursion one level down is gated on `has_single_use`, which is the lever: writing the guard as
a nested IOR whose operands are single-use temporaries — `if ((pos | n) | (pos & n))` — blocks it.
`(a | b) | (a & b) == a | b` is a bitwise identity, so this is value-preserving for *any* operands,
and `combine` folds it back to one `orrs`. That last part matters twice, because it is also what
lets `cse1` replace `mov rX, #0` with the shipped `moveq r6, r4` / `movne r4, r9`.

---

## 8. `.text` order is the call graph — and the harness reported it clean

**873 of the 1,002 differing `.text` bytes, plus every byte outside `.text`, were four functions in
the wrong place.** All four were byte-identical in content. Every per-function check passed.

`oemdiff.py` compares an *object* to the linked module. It cannot do that positionally, so it masks
every word carrying a relocation and every `B`/`BL` displacement, and compares those symbolically
instead — target symbol, addend, resolved callee. That is what makes it usable, and it is exactly
how four correctly-compiled functions sitting at wrong addresses passed as clean.

A plain `cmp` of the two modules, bucketed by symbol, finds it in one command:

```
   378  ez_probe_requst_eid208_handler
   247  ez_probe_response_eid208_handler
   143  check_probe_sync_eid208
   105  ez_probe_req_handler
```

**Why the order is what it is.** GCC emits functions in the reverse of `ipa_reverse_postorder`, a
depth-first walk of the call graph over *callers*. So a function drags its callees in front of it,
and the position of one root in the source decides where a whole chain lands. `check_probe_sync_EID`
is defined at line 48 of `ez_sc.c` and emitted near the *end*, immediately before
`ez_probe_req_handler` — the function that calls it — dragging `check_sn_valid` along in front.

Splicing `ez_probe_req_handler` in at each of the 26 top-level source positions and reading `nm -n`
off each object shows that **any** position before `check_probe_sync_eid208` reproduces the shipped
order and every position after it does not. Which of the twenty is then decided by the DECL_UID
oracle (§5): moving the function moves its eight DECL_UIDs into whichever interval it lands in, and
only one interval had a placeholder big enough to give eight back. Two independent oracles, one
answer.

Result: `.text` 1,002 → 102, `.rodata.str1.1` 208 → 0, `.rel.text` 161 → 0, `.ARM.exidx` 13 → 0,
`.symtab` 17 → 0, whole file 1,421 → 141. `.rodata.str1.1` moved because string constants are
emitted in the order the functions that use them are emitted; the other three because they are
indexed by address.

> **The rule: a per-function harness that compares symbolically cannot see a placement error.**
> Check the linked module positionally as well, bucketed by symbol.

### 8.1 Both counters under-report, in different directions

Two measurement traps, recorded because each cost real time:

- `fulldiff.py`'s shift-tolerant **structural** count charges a wrong-sized function only its size
  delta and never looks inside it, so it can rate a worse state better. Compare attempts by the raw
  positional number.
- `fulldiff.py` strips GCC's `.NNNN` uniquifiers before comparing `.strtab`, so **a `.strtab`
  scored 0 is not necessarily byte-identical**. `build/oem/uidgap.py` is the check that is.

Both maskings are necessary for the tools to be usable at all, and both must be listed explicitly
somewhere, because a field masked by every checker is verified nowhere.

### 8.2 The same shape once more, from the other side

The last time this bit, no masking rule was involved at all. `build/oem/run.sh` reported **46 of
46 OEM functions byte-identical** while the linked module still differed by 37 bytes in
`process_config_vars`, because the harness and the real build are *different compiles*: `run.sh`
compiles the two OEM translation units into a scratch directory with the flags lifted from the
last real build's `.rtw_mlme.o.cmd` and the include paths rewritten, while `build-vendorpath.sh`
copies the whole tree to the vendor's absolute path and builds it there. The two agree in
practice, which is what makes the harness worth having, but "the harness says byte-identical" is a
statement about a *different object file*, and only a full build settles it.

Both traps are now covered by standing checks rather than by discipline.
`FINDINGS-oem-catalogue.md` §22 enumerates every field each tool masks and names the check that
covers it, and the audit was tested the only way an audit can be — by reverting the §8 placement
fix and rebuilding. Both symbolic verdicts stayed exactly as they had been; the positional RAW
count went 116 → 519 and the byte-identical section count 39 → 34. **A check that has never been
observed to fire is not yet a check.** For the second trap the covering check is `build/verify.sh`,
which exports HEAD, builds it twice, asserts the SHA-256 and `cmp`s the result, and which CI runs
on every push — so a per-function verdict can no longer be the last word on anything.

---

## 9. Reproducing the vendor's bugs is not optional

Three of the byte-identical functions are byte-identical only because the reconstruction repeats a
mistake. This is a general property of this kind of work and deserves to be stated as one: **a
faithful reconstruction is a reconstruction of the vendor's defects too.**

1. **`ez_os_get_image_block` calls `kernel_read` with 4.14's argument order against 4.9's
   prototype.** 4.9 declares `int kernel_read(struct file *, loff_t, char *, unsigned long)`; the
   vendor writes `kernel_read(fp, buffer, size, &fp->f_pos)`. GCC warns and converts: the buffer
   pointer is **sign-extended into the `loff_t` offset** (`mov r2,r0; asr r3,r0,#31`), the size is
   passed as the address, and `&fp->f_pos` as the count. Writing the call correctly does not
   reproduce the function — and the sign-extension pair in the disassembly is what gave it away.
2. **`ez_wifi_preinit` frees NULL.** Under an `if (pick != NULL)` guard it emits
   `mov r0,#0; bl kfree`, so the 1 KB parse buffer leaks on every probe.
3. **`ez_set_country` never consults four of its seven tables.** `br`, `etsi`, `apec` and `other`
   are built, exported and dead; only US/EU/JP are tested.

Only (1) is load-bearing for the byte count. (2) and (3) are recorded because a reader of the
reconstructed source would otherwise assume they are transcription errors and "fix" them.

---

## 10. The last three, and exactly what decided each

Each came down to one named GCC decision, read out of the compiler's own source and confirmed in
its own dump rather than inferred. None was a structural error, and none was reachable by
respelling: about 100,000 semantically-neutral variants went through `build/oem/gen.py` and
`build/oem/lab.py` for these three functions, and the sweeps in §11 are what that negative result
looks like written down.

**`ez_strsep` — 6 bytes, 4 of 39 words, edit distance 2.** A three-pass chain, each step confirmed
in its own dump. TER (`tree-ssa-ter.c`, run inside `expand`) replaces an expression into its use
when `ssa_is_replaceable_p` holds, which requires `single_imm_use`; `t = q + 1` is used once, by
`*stringp = t`, so **the add is emitted at the store no matter which order the source writes them
in** — `-fdump-rtl-expand` shows insn 76 `mem(p_110) = 0` then insn 77 `t_129 = p_110 + 1`. Then
`auto_inc_dec` scans each block backwards, `find_inc` looks only for an inc *after* the memory
reference (FORM_POST_ADD), finds it, and `try_merge` prices the pair at 8 against 8 —
`old_cost < new_cost` is false on a tie, so it fires and the store becomes `strb r3, [r4], #1`.
The rest pointer is then in `q`'s own register, so the two `*stringp` stores are different
instructions and cross-jumping cannot merge them, where the shipped code branches to the *same*
`str r3, [r7]` the end-of-string path uses.

What closed it was denying TER the sink, not `auto_inc_dec` the fusion (§11.9 and §11.12).
`find_replaceable_in_bb` abandons a tracked expression as soon as the statement that *uses* it has
volatile operands, so writing the rest-pointer store as `*(char * volatile *)stringp = r` keeps the
add in front of the NUL store. `auto_inc_dec` then has nothing after the memory reference to fold,
`q` is still live at the store and so cannot share a register with `q + 1`, and cross-jumping
merges the two stores into the shipped one. The qualifier does not survive to the output — the
surviving store is the non-volatile one from the end-of-string path — which is exactly the point:
what the binary states is the *property* that the vendor's build did not sink the add, not the
spelling that produced it. A `goto` to a mid-loop label reproduces the same bytes.

**`ez_new_sc_ioctl` — 17 bytes, 5 of 14 words, edit distance 2.** One IRA tie, printed in full by
`-fira-verbose=9`:

```
  pref0:a0(r124)<-hr1@2000        is_null
  pref1:a1(r116)<-hr1@2000        rq
  pref2:a1(r116)<-hr2@125         rq
      Popping a1(r116,l0)  -- assign reg 2
      Popping a0(r124,l0)  -- assign reg 1
```

`rq` and `is_null` both prefer r1 at 2000; they conflict, so in `assign_hard_reg` the neighbour's
preference is subtracted from the full cost and the two cancel **exactly**. What is left is `rq`'s
weight-125 preference for r2, created by `ira-conflicts.c`'s `process_reg_shuffles` because `rq`
*dies* in `add r2, rq, #16`, whose destination is the hard argument register. r2 wins by 125,
costing `mov r2, r1` at the top. The shipped build does the opposite. Both are eight instructions;
only the assignment differs.

The 125 only decides anything because `rq` is coloured **first**, and that turns out to be a
counting problem. `assign_hard_reg` runs in the order `push_allocnos_to_stack` unwinds, which is
`bucket_allocno_compare_func`'s sort, whose first key is `ALLOCNO_FREQ` — and `REG_FREQ_FROM_BB`
returns the constant `REG_FREQ_MAX` = 1000 whenever `optimize_function_for_size_p`, so at `-Os`
**`ALLOCNO_FREQ` is exactly 1000 times the number of times the pseudo appears in the RTL**. `rq`
appears three times (the parameter copy, the null test, the address add) and `is_null` twice (the
cstore that defines it, the argument move); the allocno with *fewer* references sorts to the head,
is pushed first, and is therefore coloured last. Give `is_null` two more references and the whole
thing reverses: `is_null` is coloured first, its own hr1@2000 is cancelled by `rq`'s — still
unassigned — so every profitable register costs the same and it takes the first in ARM's
`REG_ALLOC_ORDER` that does not conflict, r3; `rq` is then coloured with no unassigned conflicting
neighbour left, keeps r1 unopposed, and the assignment is the shipped one.

Two `__asm__ __volatile__("" :: "r"(is_null))` after the guard are those two references. They emit
nothing. Equality is not enough — with three each the tie-break leaves the order as it was — and
placement is load-bearing: the same statements *before* the guard cost four bytes, and an `"+r"`
form, which also redefines the value, costs eight.

**`process_config_vars` — 79 bytes, 44 of 86 words, edit distance 5.** Three decisions in three
different passes, in a 344-byte function whose instruction *sequence* was already the vendor's.

*The `m` cstore is `tree-ssa-dom.c`, not VRP.* The shipped build materialises
`m = (pick[j-1] == ' ' && buf[i] == ' ')` as 0/1 with a conditional-move pair and then branches on
the same flags; the `movne r7, #0` half is dead, so the pair exists only because the live half is
carried by the loop PHI as an SSA name rather than as the constant 1. `-fno-tree-vrp` leaves that
argument at 1, and so do `-fno-ssa-phiopt`, `-fno-tree-forwprop`, `-fno-tree-ccp` and
`-fno-tree-sink`. The pass that folds it is DOM: `record_edge_info` has a special case for a branch
on a name with a boolean range — it records `x == 1` on the true edge of `if (x != 0)` when
`ssa_name_has_boolean_range (x)` — and `cprop_into_successor_phis` then applies that equivalence to
PHIs in *non-dominated* blocks, which its own comment says it does deliberately.
`ssa_name_has_boolean_range` is true for a `BOOLEAN_TYPE`, for any type of precision 1, **and for
an integral type whose `get_nonzero_bits` is 1** — which is precisely what a materialised `&&` is.
So no `int` spelling escapes it, and none of the ones tried did: `&` for `&&`, `!!`, `? 1 : 0`,
`u8`, `short`, a `long long` intermediate copied into `m`, `-(cond)`, `(a) * (b)`, the flag written
in both arms of the enclosing `if`, and the condition written twice so FRE unifies it. What escapes
it is the **type of the PHI**: with `_Bool m` the argument stays an SSA name and the cstore
survives, byte for byte. `_Bool` then costs the other half of the pattern, because `m & 1` on a
`_Bool` gimplifies to a no-op conversion and GCC splits the comparison into two branches; writing
the guard as `(end == 0) & (m & 1)` keeps a real `BIT_AND_EXPR`, and with it the shipped
`andeq r3, r7, #1`.

*The shared `pos = 0` has to be one statement, and the barrier has to come after it.* `uncprop`
rewrites all seven main-path `pos = 0` PHI arguments into the guard temp, and out-of-SSA's coalesce
costs accumulate **per edge** — `add_coalesce` adds, it does not take a maximum — so seven beats
`pos`'s own two, and the expand dump prints the verdict as `pos_5 & _32 : Success` beside
`pos_5 & pos_6 : Fail due to conflict`. The temp lands in `pos`'s partition, the `orr` writes
`pos`'s register, and `pos` needs a second register plus a latch copy. Note the symmetry with §7:
the *same* pass (`uncprop`) that closed `ez_set_new_sc` by firing is what held this function open by
firing — and the fix was not to block it but to remove the seven arguments it had to work on.
Blocking it directly, by giving the guard a type `gimple_can_coalesce_p` refuses, fixes the
registers and breaks the layout instead: the seven copies become real blocks, and
`reorder_basic_blocks_simple` — which at `-Os` does not sort at all, but walks the block chain
handing each tail to the *first* single-successor predecessor it meets — then gives the loop tail
to the guard-true arm. The way out is neither: write the tail once. A bare `goto` is not enough
either, because `pos = 0` is then DCE'd into the PHI argument, the block becomes an empty forwarder,
and `cleanup_cfg` deletes it, putting the copy back on all six edges. What keeps the block is a
real **use** of the stored value, which is what an `asm` that reads `pos` back provides. And it has
to come *after* the store: `can_replace_by` in `cfgcleanup.c` accepts two sets of the same
destination when one source is a `CONST_INT` and the other carries an equal `REG_EQUAL` — which is
exactly the guard-true arm's own copy — so with the `asm` last the block's final insn is an
`ASM_OPERANDS`, `old_insns_match_p` rejects the pair on its first `GET_CODE` test, and the arm
keeps its own `movne r6, #0` / `movne r2, r6` as shipped.

*Three registers on the reference count.* With `build/oem/align.py` reporting edit distance 0 over
all 86 instructions, all that was left was which register each local got — `ez_new_sc_ioctl`'s rule
again, one function up. `end` has to out-count `j` to be coloured before it, and the guard temp has
to out-count `buf`, whose thread carries an argument-register copy worth 4000. Three more empty
`asm`s, each placed where the value it names is already live so that nothing else moves, supply the
references. Placement is not free here either: the same `asm` one statement earlier reorders
`cmp r1, #35` and `str r3, [sp, #12]`, and one statement later costs an instruction. Seven
placements were compiled; two give zero.

---

## 11. Refuted conclusions and dead ends

1. **"The reconstructed kernel fragment is right because `sizeof(struct module)` is 384."**
   Refuted in §2. It reaches 384 by disabling nine unrelated options; the vendor reaches it through
   the `CPU_V7` cache-line width with those options still on. A single scalar constraint has many
   solutions. The refutation came from structs the probe was not being scored on.
2. **"The offset histogram shows thirteen struct-layout problems."** Refuted in §4: every row is one
   half of a split immediate, and they recombine to a single `+1312`.
3. **"`rtw_efuse_analyze`'s four bytes are register allocation around a `printk`."** Recorded as
   such in `FINDINGS-byte-gap.md` §4.2 and refuted in `FINDINGS-oem-catalogue.md` §14: it is a
   semantic fix, a missing brace, and the register effect is downstream of it.
4. **"`_rtw_skb_alloc`'s 92 bytes are a patched `skbuff.h` inline in the vendor kernel."** One of two
   observationally-equivalent hypotheses in `FINDINGS-byte-gap.md` §4.1. Refuted by construction:
   the driver-side patch, compiled against *unmodified* vendor headers, reproduces the function
   exactly. The detail that mattered was that the `in_interrupt()` ternary is written out at both
   call sites rather than hoisted into a `gfp_t` local — the shipped code CSEs the `preempt_count`
   load but selects the mask twice.
5. **"The four misplaced functions were fine; the harness said so."** §8. Every per-function check
   passed on all four. The harness was right about content and structurally blind to position.
6. **`ez_new_sc_ioctl`'s spelling sweep — a clean negative.** Swept and unmoved: five spellings of
   the third argument, seven types for the flag, four spellings of the null test, guard clause vs
   `if`/`else` vs a `ret` variable vs `goto`, passing a literal `0` instead of the flag (identical
   code), computing the address before and after the branch, a `static` helper, and
   `unlikely()`/`__builtin_expect`. None moves the tie, and `unlikely()` provably cannot: at `-Os`
   `REG_FREQ_FROM_BB` is a constant, so a reference in the cold error arm and one on the hot path
   contribute identically — not "not enough", but not at all.
7. **`ez_strsep`'s spelling sweep — also clean.** Ruled out, all compiled and scored: store order
   both ways; a named temporary; `p = q + 1` before or after; `*q++ = '\0'`; `*stringp = ++q`;
   `q += 1`; `&q[1]`; `q + sizeof(char)`; a cast through `unsigned long`; `(*stringp)++`; four ways
   of carrying the walk pointer; `char` and `u8` for the character; `for(;;)` and `while(1)`. The
   two that *do* block TER both break something else: advancing `p` before the delimiter test
   removes the add entirely, and breaking out to a single `*stringp = r` after the loop puts the
   epilogue at the end of the function instead of at offset 64. What the sweep left behind was not
   a spelling of the expression at all but a property of the statement that *uses* it (§10).
8. **`process_config_vars`'s guard sweep.** Ruled out: `(pos | n) == 1` and `> 0` (block the
   assertion but need a separate `cmp`); `(int)`, `(s32)`, `(u32)` casts and a temporary of another
   type (`c_common_truthvalue_conversion` strips a widening `NOP_EXPR`, and TER folds the temporary
   into the compare); `& 1`, `& 3`, `& 0xff`, `pos | (n & 1)`, `% 2`, `<< 0`, `>> 0`, `* 1`, `/ 1`,
   `+ 0`, `- 0`, `^ 0`, `!!(pos | n)`, `pos || n`, `n || pos` — VRP's own
   `simplify_bit_ops_using_ranges` removes the mask in vrp1 and vrp2 and then sees the bare IOR.
9. **`-fno-auto-inc-dec` as a fix for `ez_strsep`.** Measured as a control only: it gives the right
   order but the wrong registers, and costs two instructions in the loop, where the same pass
   produces the shipped `ldrb r3, [r5], #1`. The vendor's flags are fixed, so it was never
   shippable; it is recorded because it proves the pass is the right one and a *global* denial is
   the wrong shape of lever.
10. **Moving `check_sn_valid` instead of `ez_probe_req_handler` (§8).** Tried and rejected: it is
    reachable only through `check_probe_sync_EID`, so `.text` does not move, but it changes which
    `.LANCHOR` offsets `check_sn_valid` uses for `DeviceInfo` and `null_sn`, and the function stops
    matching.
11. **"`process_config_vars`'s cmov pair dies because VRP proves the flag is 1 on the taken edge."**
    That was this document's own reading while the function still differed, and it is wrong.
    `-fno-tree-vrp` leaves the PHI argument at 1, and so do `-fno-ssa-phiopt`, `-fno-tree-forwprop`,
    `-fno-tree-ccp` and `-fno-tree-sink`; the pass is `tree-ssa-dom.c`, through the boolean-range
    special case in `record_edge_info` (§10). The correction is not pedantry, because it moves the
    lever: VRP would have had to be attacked by changing the *value*, and DOM's special case is
    keyed on the *type*, which is why a `_Bool` closes it and no `int` spelling does.
12. **"Blocking the `auto_inc_dec` fusion is enough for `ez_strsep`."** Refuted with the pass's own
    debug counter, which is what a `dbg_cnt` is for. There are exactly three folds in that
    translation unit before the delimiter path, so `-fdbg-cnt=auto_inc_dec:2` blocks that one and
    leaves the loop's shipped `ldrb r3, [r5], #1` alone. The result is
    `mov r3, #0 ; add r4, r4, #1 ; strb r3, [r4, #-1] ; str r4, [r7]` — five instructions and four
    bytes too long, because with the add still *after* the store `q` dies at the add, IRA gives the
    add's result `q`'s own register, and post-reload rewrites the pair with a `-1` displacement.
    The requirement is one pass earlier: the add has to be in front of the store, which is TER's
    decision. Register allocation has no such counter — `grep dbg_cnt ira-*.c` is empty — so the
    same measurement is not available for the other two functions.
13. **The cross-jumped duplicate as an IRA reference device — sound, and inapplicable here.** Two
    identical `if`-arms are counted by IRA and then merged away by `pass_jump2` after reload, so
    they add references at zero cost in the output. It was the one construct `ez_new_sc_ioctl` had
    not tried. It does not apply: the duplicated body has to end in a `GIMPLE_COND` or
    `tree-ssa-tail-merge` removes it before RTL ever sees two copies, and every condition available
    to write in this function is over `is_null` or `rq`, whose ranges VRP already knows. A repeated
    `if (is_null) return -1;` after the guard is deleted outright; `return -is_null;` folds to
    `-1`; a second null test is unified by FRE. **A device that needs a surviving conditional is
    unusable in a function where every candidate conditional is provably redundant** — which is why
    an empty `asm`, which is not a conditional at all, is what closed it.

---

## 12. What is honestly not recoverable

Stated plainly, because the counting oracles of §5 are easy to over-read.

**65 declarations that emit no code.** Every DECL_UID interval in both OEM files wanted more
declarations than the reconstruction has — 47 across `ez_sc.c`, 18 across `ez_wifi_config.c`. The
kernel builds with `-Wno-unused-variable` and `-Wno-unused-but-set-variable`, so unused locals, and
`static` helpers that `-Os` inlines and deletes, cost DECL_UIDs and leave no other trace. **Which**
they were is not recoverable; **how many**, and **between which two functions**, is pinned exactly.
Each interval therefore carries one placeholder of exactly the right size, named `*_uid_gap_*` and
commented with the interval it stands for, and the header comment on the first one in each file
says plainly that they are placeholders rather than recovered vendor code.

**39 of the 60 lines above `collect_bss_info`.** Accounted for by count, not by content (§5). They
are reproduced as a labelled comment block, which is the whole of their observable effect.

**The vendor's actual source text.** The reconstructed guard in `process_config_vars` is a
value-preserving rewrite chosen because it is the only spelling found that reproduces both the
single `orrs`/`beq` and `n`'s survival across the calls. The vendor's own spelling is not
recoverable from the binary. This is the general case, not an exception: **all 46 OEM functions
compile to identical instructions without being the vendor's original text**, and nothing in a
binary can distinguish two sources that compile the same.

**Six empty `asm` statements, a `_Bool` and a `goto`.** The constructs that closed the last three
functions were chosen for the compiler, not for a reader, and each is commented as such at its
site. Two `asm`s in `ez_new_sc_ioctl` and three in `process_config_vars` exist only to raise an RTL
reference count, because IRA's colouring order at `-Os` *is* that count and no ordinary C reaches
it; a fourth in `process_config_vars` keeps a basic block alive by using the value stored in it;
`_Bool m` is not a plausible vendor choice for a value used as `m & 1`, but it is the only way
found to keep the loop PHI out of `ssa_name_has_boolean_range`; and `goto zero_pos` is the one
place where §7's rule is deliberately not applied, because that tail appears once with six
predecessors rather than twice, which is what a label is for. None of these is forced by the
binary — any source producing one `pos = 0` statement, or two more references to `is_null`, would
do — and none is offered as the vendor's. **Byte-exactness means the object code is the vendor's.
It does not mean the text is**, and these six `asm`s are where the distinction is most visible.

---

## 13. What generalises, and what does not

**Generalises.**
- Any ELF that defines `__this_module` publishes `sizeof(struct module)` as a symbol size; any
  driver that calls `netdev_priv()` publishes `ALIGN(sizeof(struct net_device), 32)` in an
  immediate. Both are exact numeric targets for reconstructing a kernel `.config`, and neither
  needs a disassembler.
- An empty `depends=` alongside a reference to a subsystem's symbols proves that subsystem is
  built in. This is cheap and it is a proof, not an inference.
- Preferring one out-of-line helper over its sibling (`kmem_cache_alloc` vs
  `kmem_cache_alloc_trace`) fingerprints the config that generated the inline code around it.
- Anything a compiler emits **once per something** is a counting oracle: `.ident` per translation
  unit, `STT_FILE` per input file, `DECL_UID` per declaration, clone counters per
  `constprop`/`part` decision. Counting bounds what is missing even when it cannot be identified,
  and two counting oracles that agree are much stronger than one.
- Reading `(our offset → their offset)` out of matched instructions localises a struct-layout error
  to a single scalar — provided split immediates are recombined first.
- A shared tail is evidence of duplicated source. A `goto` in a reconstruction is a hypothesis.
- A per-function harness that compares symbolically cannot see a placement error. Check the linked
  artefact positionally, bucketed by symbol, as a separate standing check — and prove the check
  fires by reverting a known fix, because a check never observed to fire is not yet a check.
- When a compiler optimises for size, decisions that look like heuristics collapse into counts.
  `REG_FREQ_FROM_BB` returns a constant under `optimize_function_for_size_p`, so `ALLOCNO_FREQ` is
  exactly 1000 times the RTL reference count and IRA's colouring order is a sort on that number. An
  allocation tie is then arithmetic, not taste — and, as a corollary worth as much as the rule,
  block frequencies do not exist at all, so `unlikely()` cannot move such a tie by any amount.
- **A decision keyed on a type cannot be reached by respelling a value.** DOM's boolean-range
  special case is keyed on the PHI's type, and `uncprop` is bounded by `gimple_can_coalesce_p`,
  which compares `TREE_TYPE` pointers. Both were swept against for thousands of value-preserving
  spellings before the type was noticed. Ask what the pass tests before enumerating what to write.
- A pass that carries a `dbg_cnt` can be interrogated one site at a time, which converts "which of
  these two passes decides it" from an argument into a measurement (§11.12).

**Does not generalise, or not yet.**
- The `-Os` block-layout rule (§7) is a GCC 6 fact: `reorder_basic_blocks_simple` skipping its edge
  sort under `optimize_size`. Do not carry it to GCC 4.9/5.4 or to GCC 7+ without re-deriving it.
- The `.text`-order rule is GCC-specific (reverse `ipa_reverse_postorder`) and interacts with
  `-ffunction-sections` and linker ordering; here neither was in play.
- The three that closed last were register-allocation and statement-placement decisions made after
  every source-level fact had been fixed. Nothing in §§2-8 reaches them, and the sweeps in §11 are
  the evidence for that. What did reach them was reading the deciding pass's own numbers —
  `-fira-verbose=9`'s push order, `-fdump-rtl-expand-details`'s coalescing verdicts — and then
  building a construct that changes what that pass *sees* rather than what the source says. **That
  method generalises; the three constructs do not.** They are GCC 6.5.0 facts, two of them are not
  C anyone should write, and on another compiler the first step would be to re-derive the rule and
  the last would be to expect a different device.

---

## 14. Provenance

Every number in this document comes from `README.md`, `PLAN.md` and the `FINDINGS-*.md` files in
the reconstruction tree, and from the commit log, all read at the byte-exact state of `main`. No
claim here was measured fresh for this document, and none should be quoted as if it were: where a
figure matters, re-run `build/verify.sh`, which exports HEAD, builds it twice and asserts the
SHA-256 — and `cmp`s the result as well if it is pointed at a copy of the shipped module.

Two corrections are recorded inline rather than silently applied. §4 corrects the brief that
prompted this document, which described the offset-differential trap as literal-pool loads
masquerading as struct offsets when it is split-immediate recombination. §11.11 corrects *this
document's own* earlier reading of `process_config_vars`: the cmov pair is folded away by
`tree-ssa-dom.c`, not by VRP, and the difference decided how the residual was finally attacked. One
internal disagreement between the FINDINGS docs is recorded in `FINDINGS-oem-catalogue.md` §5
itself and is repeated here without adjudication: the `rtw_mlme_ext.c` `__LINE__` delta is 60 in
the OEM catalogue and 61 in `FINDINGS-driver-config.md`, because `__LINE__` inside a multi-line
`RTW_INFO` invocation evaluates one higher than the line its text starts on.

The reproduction is byte-identical. The reconstructed source is not the vendor's text, will not
become so, and §12 is the honest statement of what separates the two.
