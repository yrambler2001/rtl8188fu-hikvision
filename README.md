# rtl8188fu-repro

A byte-level reproduction of the `8188fu.ko` shipped in a Hikvision/EZVIZ IP
camera firmware (`root_b240427`), together with the reconstructed source of the
two OEM translation units that are in no public Realtek release.

**Current state: 116 of 1,918,056 bytes differ — 0.0060% of the file**
(a plain positional `cmp`; the shift-tolerant "structural" count in
`fulldiff.py` says 192, and §6 explains why the two disagree).

**39 of the 41 sections are byte-identical**, including `.rodata`,
`.rodata.str1.1`, `.data`, `.bss`, `.symtab`, `.strtab`, `.modinfo`,
`.comment`, all twelve relocation sections and all four exidx sections. Every
one of the 3,909 function symbols is at the shipped **address** with the
shipped **size**, all 879 `__func__.NNNN` uniquifiers match, and all 38,970
relocations match. `.text` is exactly 975,780 bytes.

Only two sections still differ:

| section | bytes | what |
|---|---:|---|
| `.text` | 96 | two functions out of 3,909, both the right size, both differing only in which register the allocator picked |
| `.note.gnu.build-id` | 20 | an SHA-1 over the linked output; converges last, by construction |

---

## 1. What the module is, and how we know

The shipped module is unstripped, so it carries its own provenance:

| | |
|---|---|
| `version` | `v5.15.3-6-g1a2e952f9.20230217` |
| `author` | Realtek Semiconductor Corp. |
| `alias` | `usb:v0BDApF179...` → RTL8188FTV/FU (`0bda:f179`) |
| `vermagic` | `4.9.129 mod_unload ARMv7 p2v8` |
| `.comment` | `GCC: (arm_multilib_uclibc_20200924) 6.5.0` |
| build path | `/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/` |
| build time | `Dec 25 2023` `20:43:27` (and `20:43:30` for one OEM file) |
| ARM attrs | CPU v7-A, FP VFPv2, no `Tag_ABI_VFP_args` (soft-float ABI), `Tag_ABI_optimization_goals: Aggressive Size` (= `-Os`) |
| SoC | Fullhan FH865X (Cortex-A7), from the kernel's `mach-fh` struct layouts |

Everything below was derived from the binary. Nothing was obtained from the
vendor: `opensource.hikvision.com` publishes no packages at all (all 131 model
rows have `N/A` in both the *License* and *Source* columns), and no public
repository contains any `ez_*` symbol from this driver.
`FINDINGS-oem-catalogue.md` section 0 records that search.

## 2. Provenance chain

Realtek's git is internal; GitHub's commit index has zero hits for
`1a2e952f9`. Every public "rtl8188fu" repo begins with a tarball import, and the
popular ones (ulli-kroll, kelebek333) are on the 2017 `v4.3.23.6` codebase — a
different driver generation. So this repo reconstructs a **release lineage**
instead, one commit per Realtek drop, in date order, so that
`git log -p --follow <file>` and `git blame` work at release granularity:

```
v5.11.5      OpenIPC/realtek-wlan
v5.11.5.2    OpenIPC/realtek-wlan
v5.11.5.4    OpenIPC/realtek-wlan   (v5.11.5.4-0-g65b8f0aad.20220413)
v5.15.3      pristine vendor tarball  <-- the source of the shipped binary
```

On top of that sits the reconstruction: the OEM sources, the recovered driver
configuration, and the small number of vendor edits to Realtek's own files.

## 3. The barriers, and how each was closed

| # | barrier | status |
|---|---|---|
| 1 | vendor compiler: `.comment` says `arm_multilib_uclibc_20200924` | **closed** — `FINDINGS-toolchain.md` |
| 2 | vendor kernel tree + `.config` (Fullhan FH865X, Linux 4.9.129) | **closed** — `FINDINGS-vendor-kernel.md` |
| 3 | driver `#ifdef` configuration | **closed** — `FINDINGS-driver-config.md` |
| 4 | build path baked into `.rodata` by `__FILE__`, and `__DATE__`/`__TIME__` | **closed** — `FINDINGS-byte-gap.md` §3 |
| 5 | OEM sources `ez_sc.c` / `ez_wifi_config.c` (46 functions) not in any release | **reconstructed** — 44/46 byte-identical, `FINDINGS-oem-catalogue.md` |
| 6 | `DECL_UID` uniquifiers (`__func__.NNNN`) in `.symtab`/`.strtab` | **closed** — 879/879, `.strtab` byte-identical, `FINDINGS-oem-catalogue.md` §11 |

### 3.1 The compiler

`arm_multilib_uclibc_20200924` is not a public toolchain, but it is *only* GCC's
`--with-pkgversion=` string: GCC writes `.ident "GCC: (" <pkgversion> ") "
<version>`, and that string reaches `.comment` and nothing else. The compiler
underneath is stock **GCC 6.5.0**.

That is proven, not assumed. `build/build-gcc-vendor.sh` rebuilds GCC 6.5.0 from
the FSF release tarball with the kernel.org crosstool prebuilt's own configure
options plus that one string, and **all 158 object files it produces are
byte-identical to the stock compiler's once `.comment` is removed**. `.comment`
went from 9,347 differing bytes to 0. Binutils is deliberately *not* rebuilt:
the stock 2.32 in the same prebuilt already assembles every matching function
identically.

`nolibc` is correct — kernel modules are freestanding, so the uclibc/glibc
distinction in the vendor's toolchain name cannot reach code generation.

### 3.2 The kernel

`vermagic` pins 4.9.129 and ARMv7; the struct layouts pin the vendor tree.
`FINDINGS-vendor-kernel.md` recovers it: stock Linux 4.9.129 with the Fullhan
BSP patch `0000-fh8852-kernel-4.9.129.vendor.patch` and nothing else, configured
with `arch/arm/configs/fh8856v200_defconfig`. That BSP's only board choice does
`select CPU_V6`, which stamps `vermagic` "ARMv6"; the camera is an FH865x
(Cortex-A7) and the module says ARMv7, so `build/prepare-vendor-kernel.sh` flips
that one `select` to `CPU_V7`. With that, `vermagic` and all 15 ARM ELF
attributes match exactly and every kernel-header-shaped struct-offset difference
disappears from the offset histogram.

### 3.3 The driver configuration

Recovered from the binary by three oracles: the symbol set, struct sizes read
back out of load/store immediates, and the string set.
`FINDINGS-driver-config.md` has the derivation; the settings are in the
Makefile:

| setting | evidence |
|---|---|
| `-Os` (not Realtek's default `-O1`) | `Tag_ABI_optimization_goals: Aggressive Size` |
| `CONFIG_MP_INCLUDED = n` | `rtw_mp.o`, `ioctl_mp.o` absent |
| `CONFIG_WAPI_SUPPORT = n` | `rtw_wapi.o` absent |
| `CONFIG_RTW_IPCAM_APPLICATION = y` | force-enables monitor; binary has `rtw_recv_monitor` |
| `CONFIG_WIRELESS_EXT` in kernel | binary has the `rtw_wx_*` handlers |
| USB-only, ARMv7 | no `platform_*_sdio.o`; ARM attrs |
| `CONFIG_APPEND_VENDOR_IE_ENABLE = y` | `sizeof(struct mlme_priv) == 4168`; `rtw_vendor_ie_*` symbols |
| `CONFIG_POWER_SAVING = n` | 40 LPS/IPS functions absent; every `CONFIG_LPS`/`CONFIG_IPS`-guarded string absent |
| `CONFIG_TXPWR_LIMIT_EN = y` | `rtw_tx_pwr_lmt_enable` is in `.data` with value 1 |
| `CONFIG_AUTO_NOTCH_FILTER` defined | `phy_SpurCalibration_8188F` is 220 bytes shorter |
| `CONFIG_PLATFORM_OPS` **not** defined | binary has `platform_wifi_power_on`/`_off` |
| `REALTEK_CONFIG_PATH = "/dav/"` | `rtw_phy_file_path` resolves to that string |
| `CONFIG_EZ_WIFI = y` | the two OEM translation units |

On per the symbol table: 80211K, WNM, MBO, 80211R, BTM_ROAM, IOCTL_CFG80211,
LAYER2_ROAMING, IEEE80211W, 80211D, PROC_DEBUG, BR_EXT, NAPI, GRO, NETIF_SG,
AP + NATIVEAP_MLME, P2P, WFD, radiotap/monitor. Off: MESH, MULTI_AP,
CONCURRENT, MCC, TDLS, BT_COEXIST, BEAMFORMING, 80211AC_VHT, WAPI, MP.

### 3.4 The build environment

Two things about the *environment* rather than the sources leak verbatim into
`.rodata.str1.1`:

* **`__FILE__`.** Exactly two strings in the whole module are path-shaped, both
  absolute, both under
  `/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/`.
  They come from `RT_ASSERT_RET()` in `core/efuse/rtw_efuse.c` and `WARN_ON()`
  in `core/monitor/rtw_radiotap.c`. The kernel tree's path does not leak at all,
  so only the driver tree has to be relocated — `build/build-vendorpath.sh`
  copies it to exactly that path and builds there.
* **`__DATE__` / `__TIME__`.** `core/rtw_debug.c` prints `build time: %s %s`.
  GCC 6.5.0 predates `SOURCE_DATE_EPOCH` (verified: it ignores the variable), so
  the values are pinned with `-D` plus `-Wno-builtin-macro-redefined`.
  `ez_wifi_config.c` carries its own copy three seconds later — `20:43:30` —
  which is why `build/oem/run.sh` compiles the two OEM units with different
  `__TIME__` values.

### 3.5 The OEM code

`ez_sc.c` and `ez_wifi_config.c` — 46 functions, 8,736 bytes of `.text`, nine
`.bss` and eight `.data` objects and 115 strings — exist in no Realtek release.
Their names came out of the shipped `STT_FILE` symbols, which `ld -r` keeps one
of per input object with that object's local symbols grouped under it; that
grouping gave each file's exact `.text`/`.rodata`/`.data`/`.bss` ranges, and the
`STT_FILE` order gave the link order (they are appended to `_OS_INTFS_FILES`
right after `os_dep/linux/rtw_rhashtable.o`).

Both files, their data objects, all 115 strings and the four public call sites
they patch (`rtw_ioctl`, `OnProbeReq`, `OnProbeRsp`,
`rtw_usb_primary_adapter_init`) are reconstructed behind `CONFIG_EZ_WIFI`.
`FINDINGS-oem-catalogue.md` is the full catalogue: what each function does, how
each fact was read out of the binary, the GCC 6.5.0 `-Os` idioms that had to be
learned, and three vendor bugs that have to be reproduced verbatim to get the
bytes (a `kernel_read()` called with the 4.14 argument order against 4.9's
prototype, a `kfree(NULL)`, and four dead country-code tables).

### 3.6 The uniquifiers

GCC appends `.` plus the declaration's `DECL_UID` to file-scope and
function-local statics, and `DECL_UID` counts **every** declaration the front
end creates, headers included. The 879 such symbols in the shipped `.symtab` are
therefore an exact statement of how many declarations each of the vendor's
translation units saw before each function — and they were 726-symbols wrong
here, invisibly, because the scoreboard strips the suffix before comparing.

Reading them (`FINDINGS-oem-catalogue.md` §11) says the vendor's globally
visible OEM header carried the types and the extern objects but **not** the
function prototypes: those were declared where they are called. Splitting
`include/ez_wifi.h` that way, and putting the prototypes in
`include/ez_wifi_fn.h`, took the mismatch from 726 symbols to 16. It also
constrains the vendor's *source order*, which `.text` order alone cannot:
several OEM functions were in the wrong place and have been moved.

Source order and `.text` order are two different constraints and both have to
be satisfied. `.text` order is the reverse of `ipa_reverse_postorder`, a
depth-first walk of the call graph, so a function drags its callees in front of
it: `check_probe_sync_EID` is defined at line 48 of `ez_sc.c` and emitted near
the end, immediately before `ez_probe_req_handler`, which calls it. Putting
`ez_probe_req_handler` where the uniquifiers first suggested left that whole
chain after the three EID208 handlers and cost 1,280 bytes across five sections
— invisibly, because the per-function harness compares symbolically.
`FINDINGS-oem-catalogue.md` §20 has the derivation; the answer is that it goes
immediately after `check_probe_sync_EID`, which is the only position that
satisfies both.

The remaining 65 declarations the oracle demands emit no code — the kernel
builds with `-Wno-unused-variable` — so **which** they were is not recoverable
from the binary. **How many**, and **between which two functions**, is pinned
exactly, so each interval carries one clearly-labelled placeholder of that size
(`*_uid_gap_*`, an enum or a typedef, emitting nothing). With those, all 879
uniquifiers match and `.strtab` is byte-identical. They are placeholders, not
recovered vendor code, and are commented as such.

## 4. Result

| metric | result |
|---|---|
| `vermagic` | **exact match** — `4.9.129 mod_unload ARMv7 p2v8` |
| ARM ELF attributes | **identical** (all 15 tags) |
| `.modinfo` | **byte-identical** (9,246 bytes: params, descriptions, alias, version) |
| `.comment` | **byte-identical** (6,837 bytes) |
| `.rodata`, `.rodata.str1.1`, `.data`, `.bss`, `__param`, `__ksymtab*` | **byte-identical** |
| `.ARM.exidx` and all 3 other exidx sections | **byte-identical** (3,909 unwind entries) |
| `.strtab` | **byte-identical** (124,098 bytes) |
| `.symtab` | **byte-identical** (172,496 bytes): uniquifiers, order, `st_size` **and `st_value`** |
| relocation sections | **all 12 byte-identical** (38,970 relocations) |
| `.text` | **exactly 975,780 bytes**, every symbol at the right address and the right size |
| compiled source files | **159 / 159** |
| function symbols | **3,909 / 3,909**, none missing, none extra |
| byte-identical functions in `.text` | **3,907 / 3,909** |
| local symbol uniquifiers | **879 / 879** |
| byte-identical sections | **39 / 41** |
| **whole file** | **116 of 1,918,056 bytes differ (0.0060%)** |

### What still differs

| function | bytes | words | edit distance | cause |
|---|---:|---:|---:|---|
| `process_config_vars` | 79 | 44 of 86 | 5 | Two named GCC decisions. `uncprop` rewrites all seven main-path `pos = 0` PHI arguments into the guard temp, and out-of-SSA's coalesce costs accumulate *per edge*, so seven beats pos's own two: the `orr` writes pos's register and pos needs a second one plus a latch copy. And the shipped build materialises `m` with a dead `moveq #1` / `movne #0` pair where ours branches straight to the shared `m = 1`, because VRP proves the flag is 1 on the taken edge. `FINDINGS-oem-catalogue.md` §17 |
| `ez_new_sc_ioctl` | 17 | 5 of 14 | 2 | One IRA decision, read out of `-fira-verbose=9` and then out of `ira-color.c`: the colouring order is `bucket_allocno_compare_func`'s, whose first key is `ALLOCNO_FREQ` — and at `-Os` that is exactly 1000 × the number of RTL references. `rq` has three references and `is_null` two, so `rq` is coloured first and takes r2 on a weight-125 preference. Give `is_null` two more references and the order flips and the function is byte-identical; no ordinary-C spelling that adds them has been found. §21 |

Plus 20 bytes of `.note.gnu.build-id`, which is an SHA-1 of the two.

`ez_strsep` closed during this pass: `tree-ssa-ter.c` was sinking `q + 1` past
the NUL store, `auto-inc-dec.c` was then folding the pair into a
post-increment, and the two `*stringp` stores stopped being the same
instruction so cross-jumping could not merge them. §18.

All three were searched mechanically, not guessed at: about 90,000
semantically-neutral spellings through `build/oem/gen.py` and
`build/oem/lab.py`, and the passes that decide each of them were read out of
GCC 6.5.0's own source and confirmed in its dumps rather than inferred. §10 and
§17–21 say what was swept and what was ruled out.

## 5. Reproducing it

### 5.1 What you need

| | |
|---|---|
| the shipped module | `8188fu.ko`, 1,918,056 bytes, SHA-256 `a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13` |
| the vendor kernel tree | stock Linux 4.9.129 + `0000-fh8852-kernel-4.9.129.vendor.patch` (Fullhan FH8852/FH8856 BSP), 752 MB |
| Docker | any host; the images are `linux/arm64` (they run x86_64 too, the compiler prebuilt is the arm64-hosted one) |
| ~3 GB of scratch and ~15 minutes | for the GCC rebuild, which is a one-off |

### 5.2 Build

```sh
# 1. base image: Debian bullseye + kernel.org crosstool GCC 6.5.0 arm-linux-gnueabi
docker build --platform linux/arm64 -t rtl8188fu-build build/

# 2. vendor-kernel image
docker build --platform linux/arm64 -f build/Dockerfile.vendor \
             -t rtl8188fu-build-vendor build/

# 3. container, with the driver tree and the vendor kernel tree mounted
docker run -d --name fuv --platform linux/arm64 \
    -v "$PWD":/src \
    -v /path/to/linux-4.9.129-fullhan-pristine:/vendor-src:ro \
    -v /path/to/dir/containing/8188fu.ko:/orig:ro \
    rtl8188fu-build-vendor sleep infinity

# 4. configure the kernel tree (copy, CPU_V6 -> CPU_V7, fh8856v200_defconfig,
#    modules_prepare).  ~3 min.
docker exec fuv sh /build/prepare-vendor-kernel.sh

# 5. rebuild GCC 6.5.0 with the vendor's --with-pkgversion.  ~13 min, one-off.
docker exec fuv sh /src/build/build-gcc-vendor.sh

# 6. build the module from the vendor's own absolute path, with the vendor's
#    build timestamp.  ~1 min.  Result is copied to ./8188fu.ko.
docker exec fuv sh /src/build/build-vendorpath.sh

# 7. score it
python3 build/fulldiff.py /path/to/original/8188fu.ko ./8188fu.ko --brief
```

`build/verify.sh` does steps 6 and 7 from a **clean `git archive` of HEAD**,
builds twice to check determinism, and prints the scoreboard, both SHA-256
hashes and `cmp`. That export reproduces the same bytes as the working tree, so
nothing the build needs is untracked.

Step 6 is the whole recipe in one script: it copies the tree to
`/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217`,
sets `-D__DATE__='"Dec 25 2023"' -D__TIME__='"20:43:27"'
-Wno-builtin-macro-redefined`, and runs kbuild against `/build/linux-vendor`.

There is also a quick path against a stock kernel.org 4.9.129
(`build/Dockerfile`, `build/build.sh`, `build/compare.sh`) which needs no vendor
tree; it reaches 55.4% byte-identical functions and is useful only as a control.

### 5.3 Iterating

A full build is about a minute. For working on a single function, don't use it:

```sh
docker exec fuv sh /src/build/oem/run.sh                  # score all 46 OEM functions, ~1 s
docker exec fuv sh /src/build/oem/run.sh --fn NAME -v     # per-instruction dump
docker exec fuv sh /src/build/oem/run.sh --score          # machine-readable: n=<words> d=<size>
docker exec fuv sh /src/build/oem/pub.sh core/rtw_mlme_ext.c OnProbeReq -v
docker exec fuv sh /src/build/oem/dis.sh 0x92220 0x94570  # annotated shipped disassembly
docker exec fuv sh /src/build/oem/ourdis.sh ez_sc NAME    # our object, one function
docker exec fuv sh /src/build/oem/asm.sh ez_sc            # our assembly, whole unit
docker exec fuv python3 /src/build/oem/uidgap.py          # the DECL_UID oracle, per interval
docker exec fuv sh /src/build/oem/uidat.sh /path/any.c    # uniquifiers of an arbitrary file
docker exec fuv sh /src/build/oem/dump.sh ez_sc -fdump-rtl-ira    # GCC internals
```

For the residuals that are compiler tie-breaks rather than semantics, don't
hand-guess C shapes — generate them. A *spec* in `build/oem/specs/` expresses
one function as a template with orthogonal, semantically-neutral axes
(declaration order, local types, temporary versus recomputation, `if/else`
versus early return, operand and short-circuit order, loop form, `switch`
versus if-chain, cached base pointer versus repeated dereference, statement
order where independent); `gen.py` splices every combination into a real copy
of the translation unit and `lab.py` compiles and scores them ten at a time,
about thirty a second:

```sh
python3 build/oem/gen.py --spec build/oem/specs/ez_strsep.py --out build/oem/lab/s1
docker exec fuv sh -c 'cd /src && python3 build/oem/lab.py \
        --unit ez_wifi_config --dir build/oem/lab/s1 --fn ez_strsep -j 10'
```

Each variant is scored three ways: `n` differing words, `d` size delta, and
`s` — the Levenshtein distance of the two instruction sequences with the
register fields blanked out. Steer by `s`: a variant that is right except for
which registers IRA picked scores nearly every word different, so `n` is
almost useless as a gradient. Results are cached by source hash;
`build/oem/lab/` is scratch and untracked.

`build/oem/oemdiff.py` compares an object file to the *linked* module, which
cannot be done positionally: bytes under a relocation are masked and compared
symbolically (target symbol, addend, and for `.rodata.str1.1` the actual
string), `B`/`BL` words by their resolved callee, intra-function branches by
their offset from the function start.

### 5.4 Scoreboards

```sh
python3 build/fulldiff.py   <shipped> ./8188fu.ko [--brief]   # whole file, every section
python3 build/offsetdiff.py <shipped> ./8188fu.ko [--fn NAME] # per-function .text
python3 build/bytecompare.py <shipped>                        # historical, function-level
```

`fulldiff.py`'s "structural" number is shift-tolerant: it matches symbols by
name rather than address, so a function that moves does not inflate the count.
Note that it deliberately strips GCC's `.NNNN` uniquifiers before comparing
`.strtab`, so a `.strtab` scored 0 there is not necessarily byte-identical —
that is what hid barrier 6 (§3.6).

## 6. Verification

```
$ python3 build/fulldiff.py /path/to/8188fu.ko ./8188fu.ko --brief
   STRUCTURAL  192 bytes differ (0.010% of the shipped 1,918,056)
   RAW         116 bytes differ positionally (0.0060%)
   byte-identical sections: 39/41

$ cmp /path/to/8188fu.ko ./8188fu.ko
/path/to/8188fu.ko ./8188fu.ko differ: char 69, line 1

$ sha256sum /path/to/8188fu.ko ./8188fu.ko
a7fcfe277c77d9e497104fd5cc12f62ccd3df851b0ff3292b035444f5d78bb13  8188fu.ko   (shipped)
b2e014d2554540023997ed39ff32371cc30925d9081528ad6ef04d4dbf2b9809  8188fu.ko   (ours)
```

`cmp` is **not** clean, and the numbers above are the honest statement of how
far this got. The first differing byte is at offset 68, inside the
`.note.gnu.build-id` SHA-1 — a hash of the two functions in §4, which cannot
match until they do. Everything before it, including `e_shoff` and the whole
section header table, is right.

**Two counts, and which to use.** `fulldiff.py`'s *structural* count matches
symbols by name and charges a function whose size is wrong only its size
*delta*, never looking inside it. That is what stops one moved function
inflating the count into the hundreds of thousands — but it rates a 344-byte
function that should be 340 at 4 bytes and a 344-byte function with 176
differing bytes at 176. **Compare attempts by the raw number.**

The same warning applies one level down and it cost this reconstruction
1,280 bytes for a while: `build/oem/oemdiff.py` compares an *object* to the
linked module, which cannot be done positionally, so it masks every relocated
word and every `B`/`BL` displacement and compares those symbolically. A
function it calls byte-identical can therefore still differ in the linked
output — and four of them did, because they were in the wrong *place*. See
`FINDINGS-oem-catalogue.md` §20. Always check the linked module positionally
as well, bucketed by symbol.

## 7. Repository layout

```
core/ hal/ os_dep/ include/ platform/   Realtek v5.15.3 + the reconstruction
  os_dep/linux/ez_sc.c                  OEM: smart config, device discovery over probe frames
  os_dep/linux/ez_wifi_config.c         OEM: config file, country code, efuse, version
  include/ez_wifi.h                     OEM types and objects (pulled in by drv_types.h)
  include/ez_wifi_fn.h                  OEM prototypes (only where they are called)
Makefile                                the recovered vendor configuration
build/
  Dockerfile, Dockerfile.vendor         the two build images
  prepare-vendor-kernel.sh              vendor kernel tree -> modules_prepare
  build-gcc-vendor.sh                   GCC 6.5.0 with --with-pkgversion
  build-vendorpath.sh                   the real build
  fulldiff.py offsetdiff.py bytecompare.py    scoreboards
  oem/                                  the per-function iteration harness
  oem/gen.py oem/lab.py oem/specs/      the variant search
  oem/align.py                          aligned side-by-side disassembly of one function
  oem/uidgap.py                         the DECL_UID oracle, per interval
FINDINGS-hardware.md                    the camera and the SoC
FINDINGS-vendor-kernel.md               barrier 2
FINDINGS-driver-config.md               barrier 3
FINDINGS-byte-gap.md                    the whole-file scoreboard and barrier 4
FINDINGS-toolchain.md                   barrier 1
FINDINGS-oem-catalogue.md               barriers 5 and 6 - the OEM code, in full
PLAN.md                                 work packages and status
```
