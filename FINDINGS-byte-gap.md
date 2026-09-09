# The whole-file byte gap

Everything measured so far (`build/bytecompare.py`, `build/offsetdiff.py`) scored `.text`
functions. That is the right instrument for "did we recover the vendor's compiler, kernel
headers and `#ifdef` set", and it is the wrong instrument for "how far is this from a
byte-identical *file*". `.text` is 51% of the shipped module; the symbol table, the string
tables, the relocation sections and `.comment` are the other half, and none of them were
being looked at.

`build/fulldiff.py` scores the whole ELF. This note records the baseline it produces, the
closing of barrier 4 (the vendor's build path), and verdicts on the three single-function
residuals.

## 1. How the scoreboard works

The tool is a self-contained ELF32-LE reader - no `readelf`, no pyelftools, ~2 s per run -
and it reports two numbers per section.

**RAW** is a strict positional byte compare plus the size delta. It is what byte-exactness
literally means, and on its own it is useless for steering work: one missing function
shifts every byte after it, so RAW currently sits at **1,228,291 / 1,918,056 bytes (64%)**
while the module is in fact 98% recovered. RAW is the number that has to reach zero; it is
not the number to optimise against.

**STRUCTURAL** is shift-tolerant. Content is keyed by what it *is* rather than where it
sits: a function by its name, a data object by its name, a string by its bytes, a
relocation by *(owning symbol, offset inside that symbol, type, target symbol)*, an ARM
unwind entry by the function it describes. It reaches zero exactly when RAW does, but it
does not move when unrelated code above it changes size. STRUCTURAL splits into

| bucket | meaning |
|---|---|
| `missing` | bytes of symbols / strings / entries present only in the shipped file |
| `extra` | ... present only in ours |
| `resized` | sum of abs(size delta) over symbols present in both |
| `content` | bytes differing inside same-size symbols, excluding relocated words and B/BL displacements |
| `reloc` | *reported, not counted*: differing bytes that a relocation covers - addends, i.e. link layout |
| `branch` | *reported, not counted*: B/BL words where only the imm24 differs - also link layout |
| `derived` | *reported, not counted*: differences that are a mechanical consequence of something already counted |

Three details matter for the numbers to mean anything:

*GCC's local-symbol uniquifier.* Local statics are emitted as `__func__.75858`, and that
counter shifts whenever anything above them in the same translation unit changes. Compared
raw, 719 of 5,723 `.strtab` strings look "shipped-only". Names are therefore compared with
the trailing `.NNNN` stripped, and the raw-name churn is reported as `derived` (20,896
bytes today) rather than as work to do.

*Same-named symbols.* A single normalised name can cover 200 different string constants
(`__func__`). Pairing those by address manufactures hundreds of bogus size differences -
an early version of the tool reported 208 "resized" objects in `.rodata` that do not
exist. They are paired by content first, then by address.

*B/BL displacements.* A call to a function in the same section is resolved by the
assembler with no relocation, so it looks like a content difference. Classifying those
separately is what took `.text`'s `content` bucket from 93 bytes in 40 functions down to
**28 bytes in 4 functions** - and those four are exactly the four `__LINE__` constants
already known to be OEM-patch artefacts.

## 2. Baseline

Both columns are the same tool on the same shipped reference; the only change between them
is barrier 4 (section 3).

| | before | after |
|---|---:|---:|
| **STRUCTURAL** | **37,993** | **37,630** (1.962% of 1,918,056) |
| RAW | 1,228,488 | 1,228,291 |
| module size | 1,890,468 | 1,890,660 |
| byte-identical sections | 16 / 41 | 16 / 41 |

Ranked, after:

| section | structural | raw | breakdown |
|---|---:|---:|---|
| `.text` | 9,692 | 733,043 | missing 9,032, extra 4, resized 628, content 28 (+13,964 reloc, +284 branch) |
| `.comment` | 9,347 | 6,741 | missing 6,678, extra 2,669 |
| `.rel.text` | 7,688 | 110,689 | missing 5,624, extra 2,064 |
| `.rodata.str1.1` | 3,493 | 154,577 | missing 3,493 |
| `.symtab` | 3,020 | 52,589 | missing 2,992, content 28 |
| `.strtab` | 1,288 | 111,016 | missing 1,281, extra 7 (+20,896 derived) |
| `.data` | 956 | 34,407 | missing 956 (+3,700 reloc) |
| `.bss` | 671 | 671 | missing 671 |
| `.rodata` | 420 | 8,448 | missing 420 (+752 reloc) |
| `.rel.ARM.exidx` | 408 | 2,035 | missing 408 |
| `.ARM.exidx` | 372 | 8,862 | missing 368, content 4 |
| `.rel.rodata` | 256 | 701 | missing 128, extra 128 |
| `.note.gnu.build-id` | 19 | 19 | content 19 |
| 28 other sections | 0 | 0-3,786 | structurally identical |

The section inventory itself is already exact: **42 sections, same names, same order, same
types, flags, alignments and entsizes**, and `.modinfo`, `__param`, `__ksymtab`,
`__ksymtab_strings`, `.gnu.linkonce.this_module`, `.ARM.attributes`, `.shstrtab` and eight
of the twelve relocation sections are byte-identical.

### Where the 37,630 bytes actually come from

Almost all of it is one thing. Attributing every bucket to a cause:

| cause | bytes | share |
|---|---:|---:|
| missing OEM code (`ez_sc.c` / `ez_wifi_config.c` and its call sites) | ~28,100 | 75% |
| GCC `--with-pkgversion` string in `.comment` | 9,347 | 25% |
| the three single-function residuals (section 4) | ~150 | 0.4% |
| `.note.gnu.build-id` (a hash of the module - converges last, by construction) | 19 | 0.05% |

The OEM attribution is not hand-waving; every section decomposes cleanly:

* `.text`: 46 absent OEM functions (8,736 bytes) plus 296 bytes of extra out-of-line
  `copy_to_user`/`copy_from_user` copies that GCC emits once per translation unit that
  needs them - the shipped module has 6 `copy_from_user` and 3 `copy_to_user` bodies to our
  5 and 1, i.e. exactly two more translation units. `resized` is 528 bytes across the four
  known OEM call sites plus 100 bytes across the three residuals. `content` is 28 bytes: 16
  in `collect_bss_info` and 4 each in `rtw_efuse_map_write`, `rtw_BT_efuse_map_write` and
  `rtw_wx_set_priv` - all `__LINE__` constants, all four already documented in
  `FINDINGS-driver-config.md` as measurements of the OEM patch. **Every other same-size
  function in the module - 1,293 of them - is instruction-for-instruction identical.**
* `.rel.text`: 703 shipped-only entries = 413 inside OEM functions + 281 inside the four
  OEM call sites + 4 in the extra `copy_*_user` bodies + 5 in the residuals; 258 ours-only
  = 254 in the OEM call sites + 4 in the residuals. Nothing else.
* `.symtab`: 187 shipped-only entries - 46 OEM functions, 86 ARM `$a`/`$d` mapping symbols
  inside the OEM code, 19 `__func__`/`__FUNCTION__` constants, 9 `.bss` and 8 `.data`
  objects, 3 extra `copy_*_user` bodies, 4 undefined symbols, and a dozen more `$d`
  markers. The `content` 28 bytes are the 7 functions whose `st_size` differs.
* the four undefined symbols only the shipped module has are `__alloc_skb` (4.1),
  `kernel_read`, `kmalloc_caches` and `kmem_cache_alloc` - the last three are the OEM code
  reading its config file and using constant-size `kmalloc()`, which is another constraint
  on WP-D.
* `.data` 956, `.bss` 671, `.rodata` 420: eight OEM country-code tables plus `ez_sync_code`;
  nine OEM `.bss` objects (`DeviceInfo`, `ez_mac_addr`, `probe_req_t`, ...); 19 OEM
  `__func__` strings and `invalid_efuse_data1/2`.
* `.ARM.exidx` / `.rel.ARM.exidx`: 46 missing unwind entries, one per OEM function. The
  single differing unwind word in the whole module belongs to `_rtw_skb_alloc`
  (`0x80a8b0b0` vs `0x80b0b0b0` - the shipped version saves `{r4, lr}`, ours does not).
* `.rel.rodata`: 16 entries on each side, all in anonymous `.rodata` (switch tables) whose
  offsets moved.

`.comment` is the one large non-OEM item and it is a single string. The section is not
merged in a `ld -r` link, so it holds one `.ident` per object file: **159 copies** of
`GCC: (arm_multilib_uclibc_20200924) 6.5.0` (43 bytes each = 6,837) against our **157**
copies of `GCC: (GNU) 6.5.0` (18 bytes each = 2,826). The copy count is itself a nice
confirmation that exactly two object files are missing. Closing this needs GCC 6.5.0 built
with `--with-pkgversion='arm_multilib_uclibc_20200924'`; the string reaches nothing but
`.comment`, so it is cosmetic for behaviour and worth 25% of the remaining byte gap. That
is a new work package, not something this pass could do.

## 3. Barrier 4 closed: the vendor's build path

### What is actually in the binary

Extracted from the shipped `.rodata.str1.1`, whole-file scan for anything path-shaped:

```
/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/core/efuse/rtw_efuse.c
/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/core/monitor/rtw_radiotap.c
```

Verified, against the earlier assumption:

* there are **exactly two** such strings and no others - a scan for `/data1`,
  `linux-4.9`, and relative `../.../*.c` forms over the entire 1.9 MB file finds nothing else;
* they are **absolute**, not relative. That follows from kbuild: an out-of-tree module
  built with an absolute `M=` compiles `$(src)/core/efuse/rtw_efuse.c`, so `__FILE__` is
  the absolute path. Our build emitted `/src/core/efuse/rtw_efuse.c` for the same reason;
* the **kernel source path does not leak at all**. No `WARN_ON`/`BUG_ON` in an inline
  kernel header survives into this module with a `__FILE__` of its own, so the kernel tree
  does not have to be relocated to any particular path. Only the driver tree does;
* the two macros responsible are `RT_ASSERT_RET()` (a file-local macro in
  `core/efuse/rtw_efuse.c` that prints `__FILE__`, `__FUNCTION__`, `__LINE__`) and
  `WARN_ON()` in `core/monitor/rtw_radiotap.c`.

The same scan turned up a second environment leak that had not been recorded:
`core/rtw_debug.c` prints `"build time: %s %s"` with `__DATE__`/`__TIME__`, and the shipped
module carries **`Dec 25 2023` / `20:43:27`**. It also carries a *second* `Dec 25 2023` and
a `20:43:30` at `.rodata.str1.1` offset 114,997 - immediately before the
`ez_read_rssi_per_ant_ioctl` strings - so one of the two OEM files prints its build time
too, three seconds later in the same build. Which of the two timestamps belongs to
`rtw_debug.c` is not a guess: both builds place its strings at offsets 2174/2183, so
`20:43:27` is ours to reproduce and `20:43:30` is a WP-D constraint.

GCC 6.5.0 **does not honour `SOURCE_DATE_EPOCH`** (tested: it still stamped the host date),
so the timestamps are pinned with `-D__DATE__=... -D__TIME__=... -Wno-builtin-macro-redefined`,
which GCC 6.5.0 accepts. `-fmacro-prefix-map`/`-ffile-prefix-map` do not exist in this
compiler and would be the wrong tool anyway - we want the genuine path.

### Reproducing it

`build/build-vendorpath.sh` copies the tree to that exact absolute path inside the
container and builds there:

```sh
docker exec fuv sh /src/build/build-vendorpath.sh
python3 build/fulldiff.py /path/to/original/8188fu.ko ./8188fu.ko
```

### Result

`.rodata.str1.1` before and after:

| | before | after |
|---|---:|---:|
| bytes | 192,890 | 193,088 (shipped 196,583) |
| strings only in shipped | 119 (3,773 bytes) | **115 (3,493 bytes)** |
| strings only in ours | 4 (82 bytes) | **0** |
| path-like differences | 2 + 2 | **0** |

The qualitative statement is the useful one: **every string our build emits is now present
in the shipped module.** The 115 that remain are OEM strings - `ez_*_ioctl` traces, the
country-code error messages, `GET AP DTAT SUCCESS`, and the second build timestamp.

One incidental WP-D signal fell out of it: eight strings appear **twice** in the shipped
module and once in ours - `CN`, `%s%sRTW: %s: rtw_efuse_mask_map_read error!`, and five
`[%s] ... append vendor ie` messages. Since `ld -r` does not merge string sections, a second
copy means a second object file contains the same literal, so the OEM sources duplicate
those exact strings.

## 4. The three residuals

### 4.1 `_rtw_skb_alloc` - 92 bytes, not resolved

The shipped function, read instruction by instruction, is:

```c
gfp_t gfp = in_interrupt() ? GFP_ATOMIC : GFP_KERNEL;
if (sz <= 1024) {
        skb = __alloc_skb(sz + 64 /* NET_SKB_PAD */, gfp, SKB_ALLOC_RX, NUMA_NO_NODE);
        if (skb) { skb->data += 64; skb->tail += 64; skb->dev = NULL; }   /* skb_reserve */
        return skb;
}
return __netdev_alloc_skb(NULL, sz, gfp);          /* = __dev_alloc_skb(sz, gfp) */
```

Ours is the tail call alone, which is what the tarball's one-line source
(`os_dep/osdep_service.c:477`) and stock `skbuff.h` produce.

What the fast path *is*, is stock 4.9's `__netdev_alloc_skb` body with `dev == NULL`
constant-folded in - its `__alloc_skb` branch, its `skb_reserve(skb, NET_SKB_PAD)`, its
`skb->dev = dev`. What is inverted is the guard: upstream takes `__alloc_skb` when the
length is *large* (`len > SKB_WITH_OVERHEAD(PAGE_SIZE)`, 3,776 here) or the gfp mask asks
for reclaim; the shipped module takes it when the length is *small* (`<= 1024`) and sends
everything else to the out-of-line function. That reads like a deliberate "don't burn a
page-frag cache entry on small RX skbs" tweak for a memory-tight camera.

Checks run, and what they showed:

* **`NET_SKB_PAD` is right in our build.** `L1_CACHE_BYTES` is 64 (`CONFIG_ARM_L1_CACHE_SHIFT=6`,
  which the CPU_V7 retarget already established), so `NET_SKB_PAD = max(32, 64) = 64`,
  matching the `add r0, r0, #64` in the shipped code.
* **The struct offsets in the shipped fast path match our headers exactly** - `skb->dev`
  at 20, `skb->data` at 148, `skb->tail` at 160. So this is not a different `struct sk_buff`;
  it is a different code path over the same layout.
* **`CONFIG_TINY_KERNEL` is not it.** It exists in the vendor tree and we already build
  with `=y`, but its only reach into anything the driver includes is
  `include/linux/netdevice.h:2078`, where it sets `NAPI_POLL_WEIGHT` to 32 instead of 64.
  It does not touch skb allocation anywhere.
* **The vendor patch does not touch skb allocation.** `0000-fh8852-kernel-4.9.129.vendor.patch`
  has 494 file diffs; the only `net/` files it touches are `appletalk/`, `rds/tcp.c` and
  `wireless/reg.c`, and it does not modify `include/linux/skbuff.h` or `net/core/skbuff.c`.
  The tree's `skbuff.h` declares `__netdev_alloc_skb` `extern` and `__dev_alloc_skb` as the
  thin inline wrapper, exactly as stock.
* **The other Fullhan modules cannot settle it.** All nine (`isp`, `enc`, `vpu`, `jpeg`,
  `nna`, `bgm`, `vmm`, `xbus_rpc`, `media_process`) were extracted and checked: **none of
  them references any skb symbol at all** - they are media/ISP modules. So the one external
  oracle that could have proved "kernel header, not driver patch" has nothing to say.
* `__alloc_skb` is referenced from exactly one function in the shipped module,
  `_rtw_skb_alloc`, and so is `__netdev_alloc_skb`. The driver's only other
  `__dev_alloc_skb` call site (`core/rtw_mem.c:143`) is compiled out in both builds, so it
  cannot act as a second witness either.

**Verdict: unresolved, and the two hypotheses remain observationally equivalent.** A
patched `__dev_alloc_skb` inline in the real FH865x BSP's `skbuff.h` and an OEM patch to
`os_dep/osdep_service.c` would produce byte-identical output here, because the driver has
exactly one call site. The circumstantial weight has moved slightly toward the *driver*
patch: `osdep_service.c` is demonstrably a patched file - six of its functions
(`rtw_is_file_readable`, `rtw_retrieve_from_file`, `rtw_division64`, `rtw_modular64`, the
`rtw_sptime_*` group) differ from ours only in BL displacements, which is what happens when
code is inserted into a file, and the OEM patch is already proven to touch four other
driver files. The reconstruction above is exact enough to be dropped into WP-D and tested.

### 4.2 `rtw_efuse_analyze` - 4 bytes, hypothesis disproved

> **CLOSED.** The analysis below is correct about the mechanism but wrong about
> the cause. The vendor's one added line in `core/efuse/rtw_efuse.c` is not a
> line that shifts register pressure - it is a **brace**, and adding it makes
> the function byte-identical. See `FINDINGS-oem-catalogue.md` section 14.

Normalising away literal-pool distances and branch displacements, **591 of 634
instructions are identical**. Every difference except one window is a `bl` displacement.
The one real difference is a six-instruction window at the end of the function: the shipped
build keeps two string-constant addresses live in `r7`/`r8` across a `printk` and selects
between them with `moveq r2, r7` / `moveq r2, r8`, while ours rematerialises one of them
from the literal pool (`ldreq r2, [pc]`, then `ldr r3, [pc]` / `movne r2, r3`). One extra
instruction, +4 bytes.

The standing hypothesis was `-fmerge-constants` behaving differently because OEM strings
are missing from the pool. **That is now disproved for this function.** Both builds have
**81 relocations inside the function against exactly the same 81 string constants**, both
literal pools hold **36 words**, and rebuilding with the correct vendor `__FILE__` path -
which lengthened the `RT_ASSERT_RET` string in this very file from 27 to 124 characters -
did not change the function by a byte. The constant pool is not the input that differs.

**Verdict: an unexplained register-allocation difference, 4 bytes.** The most likely
remaining cause is that the OEM patch to `core/rtw_efuse.c` - which we know exists, because
`rtw_efuse_map_write` and `rtw_BT_efuse_map_write` each carry a `__LINE__` one higher than
ours - also changes something inside or above `rtw_efuse_analyze` and shifts register
pressure. WP-D will settle it; it is not worth chasing before then, but it should no longer
be attributed to string merging.

### 4.3 `rtw_sptime_get` - confirmed not a difference

Confirmed and closed. Shipped 104 bytes, ours 100; **20 of 23 instructions are identical,
the two that differ are a `bl` displacement and one literal-pool distance, and the entire
size difference is a single trailing `nop {0}`** that the shipped build inserts to align
its literal pool, because the function lands at a different address once 9.6 KB of OEM code
is present. There is no code difference. Nobody should investigate this again.

## 5. What this pass could not resolve

* `.comment` (9,347 bytes, 25% of the remaining gap) needs a GCC 6.5.0 built with
  `--with-pkgversion='arm_multilib_uclibc_20200924'`. Nothing short of that reproduces the
  string honestly; `objcopy --update-section` would fake it.
  **Closed since — see `FINDINGS-toolchain.md`.** That GCC was built, `.comment` fell to 84
  bytes (the two OEM object files, and our section is now a byte-exact prefix of the shipped
  one), the whole-file total went 37,630 -> 28,368, and codegen was verified unchanged: all
  158 object files byte-identical to the stock compiler's with `.comment` removed. Every
  other number in this note still stands as written.
* `_rtw_skb_alloc` (4.1) - two hypotheses, no evidence that separates them.
* `rtw_efuse_analyze` (4.2) - 4 bytes, cause unknown, previous explanation ruled out.
  **(Since closed - see the note at the head of 4.2.)**
* `.note.gnu.build-id` is an SHA-1 over the linked module. It cannot match until everything
  else does, and it will match automatically when they do. It is listed for completeness.
* The `derived` bucket - 20,896 bytes of `.strtab` churn from GCC's local-symbol
  uniquifier renumbering - is excluded from the headline because it is downstream of the
  missing OEM code, not an independent problem. If WP-D lands and it does *not* go to zero,
  that is a signal the reconstruction is not in the same source order as the original.

## 6. Re-running

```sh
docker exec fuv sh /src/build/build-vendorpath.sh          # vendor path + vendor timestamp
python3 build/fulldiff.py /path/to/original/8188fu.ko ./8188fu.ko            # full report
python3 build/fulldiff.py /path/to/original/8188fu.ko ./8188fu.ko --brief    # scoreboard only
python3 build/fulldiff.py ... --section .rodata --top 40   # attribute one section's byte runs
python3 build/fulldiff.py ... --strings                    # every string in one file only
python3 build/fulldiff.py ... --syms                       # every symbol-table difference
```

`build/build.sh` still builds the old way (in `/src`, host timestamp) if a control is
needed; that is how the "before" column in section 2 was produced.
