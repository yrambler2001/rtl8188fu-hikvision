# Barrier 1: the vendor toolchain

> **Status: closed**, and the module now reproduces byte for byte. This note is
> the record of the work package that identified and rebuilt the compiler; its
> byte counts are that pass's, not the current state. `README.md` §4 has the
> final accounting.

The shipped module's `.comment` section says the compiler was

```
GCC: (arm_multilib_uclibc_20200924) 6.5.0
```

once per translation unit, 159 times. Ours said `GCC: (GNU) 6.5.0`, 157 times. At 43 bytes
against 18 that is **9,347 bytes - 25% of the whole remaining byte gap** - and it was the
only item in the gap that is not missing OEM code.

This note records what that string actually is, the GCC that was built to produce it, and
the verification that building that GCC changed nothing else. Headline: it worked, the
`.comment` difference collapsed from 9,347 bytes to **84** - exactly the two OEM object
files we do not have - the whole-file gap went from **37,630 to 28,368 bytes (1.962% ->
1.479%)**, and every one of the 158 object files the driver compiles to is **byte-identical**
to the one the stock compiler produced, once `.comment` is removed.

## 1. The string is `--with-pkgversion`, and here is the code that proves it

`gcc/toplev.c` in the 6.5.0 release tarball:

```c
  /* Attach a special .ident directive to the end of the file to identify
     the version of GCC which compiled this code.  The format of the .ident
     string is patterned after the ones produced by native SVR4 compilers.  */
  if (!flag_no_ident)
    {
      const char *pkg_version = "(GNU) ";
      char *ident_str;

      if (strcmp ("(GCC) ", pkgversion_string))
	pkg_version = pkgversion_string;

      ident_str = ACONCAT (("GCC: ", pkg_version, version_string, NULL));
      targetm.asm_out.output_ident (ident_str);
    }
```

`pkgversion_string` is `PKGVERSION`, which `configure` sets to `"($withval) "` from
`--with-pkgversion=` and to `"(GCC) "` when the option is absent. So the ident line reads
`GCC: (GNU) 6.5.0` on a default build - the literal `"(GNU) "` fallback above, which is why
a stock compiler's `.comment` disagrees with its own `--version` banner
(`arm-linux-gnueabi-gcc (GCC) 6.5.0`) - and `GCC: (<whatever was configured>) <version>` on
any build that sets the option. Debian's own host compiler in the same container
demonstrates the second case: `--with-pkgversion='Debian 10.2.1-6'` gives `.comment` =
`GCC: (Debian 10.2.1-6) 10.2.1 20210110`.

Nothing else reads `pkgversion_string` on a compile path. It reaches `.comment` and the
`--version` / `-v` banners, and that is the whole list.

### An outside witness

`arm_multilib_uclibc_20200924` also appears in the **kernel** banner of a sibling camera.
OpenIPC issue [#2019](https://github.com/OpenIPC/firmware/issues/2019) is a hardware report
for a Hikvision DS-2CD1043G0-IUF on the Fullhan FH8852V200, and its boot log reads

```
Linux version 4.9.129 (root@CI-HZV-FRONTEND-SLAVE-71-99)
  (gcc version 6.5.0 (arm_multilib_uclibc_20200924)) ... Thu Oct 19 11:24:38 CST 2023
```

Three things follow:

* the banner prints `version_string` then `pkgversion_string`, so `6.5.0
  (arm_multilib_uclibc_20200924)` there and `GCC: (arm_multilib_uclibc_20200924) 6.5.0` in
  our `.comment` are the same variable seen from two directions. The string is the
  pkgversion; there is no other reading of it;
* the same toolchain built the *kernel* of a different Hikvision camera, on a different
  Fullhan part, a year later - so it is a house toolchain used across a product line, not
  something that shipped with this driver;
* `CI-HZV-FRONTEND-SLAVE-71-99` is a Hikvision Hangzhou CI build slave. The toolchain is
  internal to Hikvision, which is the main reason section 6 finds nothing published.

## 2. The stock compiler, recorded verbatim

`build/Dockerfile` installs kernel.org crosstool `arm64-gcc-6.5.0-nolibc-arm-linux-gnueabi`
at `/opt/gcc-6.5.0-nolibc/arm-linux-gnueabi`. `arm-linux-gnueabi-gcc -v` reports:

```
Target: arm-linux-gnueabi
Configured with: /home/arnd/git/gcc/configure --host=aarch64-linux-gnu
  --target=arm-linux-gnueabi --enable-targets=all
  --prefix=/home/arnd/cross/x86_64/gcc-6.5.0-nolibc/aarch64-linux-gnu/arm-linux-gnueabi
  --enable-languages=c --without-headers --disable-bootstrap --disable-nls
  --disable-threads --disable-shared --disable-libmudflap --disable-libssp
  --disable-libgomp --disable-decimal-float --disable-libquadmath --disable-libatomic
  --disable-libcc1 --disable-libmpx --enable-checking=release
  : (reconfigured) <the same option list again>
Thread model: single
gcc version 6.5.0 (GCC)
```

Wrapped here; it is one line in the binary. The `: (reconfigured)` suffix is what GCC records
when the top-level configure is re-run in place, which is normal for a staged crosstool build.

Two details of that line are worth naming. The `--prefix` says
`.../x86_64/gcc-6.5.0-nolibc/aarch64-linux-gnu/...`, so Arnd builds this as a **Canadian
cross**: build machine x86_64, host aarch64, target arm. And `--without-headers` with no
`--with-sysroot` is what "nolibc" means - a freestanding compiler with no libc headers at
all. That is exactly right for kernel modules, and it is why the uClibc/glibc distinction in
the vendor's toolchain name cannot reach our output.

**Binutils, deliberately unchanged.** The same prefix carries `GNU assembler (GNU Binutils)
2.32` and `GNU ld (GNU Binutils) 2.32`, binaries dated 14 Feb 2020. 1,293 same-size
functions in the module already assemble instruction-for-instruction identically with it, so
the assembler is demonstrably right. The vendor's `20200924` date stamp is consistent with a
toolchain assembled around then, and binutils 2.32 (Feb 2019) or 2.35 (Jul 2020) would both
fit that date - but nothing in the binary poses the question, and until something does,
changing it could only break 1,293 working functions.

## 3. What was built

`build/build-gcc-vendor.sh`, run inside the existing container:

```sh
docker exec fuv sh /src/build/build-gcc-vendor.sh
```

Sources: `gcc-6.5.0.tar.xz` from ftp.gnu.org, sha256
`7ef1796ce497e89479183702635b14bb7a46b53249209a5e0f999bebf4740945` (the FSF release
checksum). Configure line, against the stock one:

| stock | ours | why |
|---|---|---|
| `--host=aarch64-linux-gnu` (build = x86_64) | `--build=aarch64-unknown-linux-gnu --host=aarch64-unknown-linux-gnu` | we are already on aarch64, so this is a plain native build of the same cross compiler. The canonical four-field triple is what `config.guess` reports here; the strings reach only the *Configured with:* banner. (An earlier attempt with Arnd's three-field form died in `configure-gmp` - *"machine \`aarch64' not recognized"* - but that was a stale `gmp-4.3.2` left in the tree, see section 5; `gmp-6.1.0` accepts it.) |
| `--prefix=/home/arnd/cross/...` | `--prefix=/opt/gcc-6.5.0-vendor/arm-linux-gnueabi` | the stock compiler stays installed at `/opt/gcc-6.5.0-nolibc` so the two can be compared |
| *(absent)* | `--with-pkgversion=arm_multilib_uclibc_20200924` | **the point of the exercise** |
| *(defaults)* | `CC=aarch64-linux-gnu-gcc CXX=aarch64-linux-gnu-g++ CFLAGS='-O2 -fcommon' CXXFLAGS='-O2 -fcommon'` | host build flags only; see below |
| everything else - `--target=arm-linux-gnueabi --enable-targets=all --enable-languages=c --without-headers --disable-bootstrap --disable-nls --disable-threads --disable-shared --disable-libmudflap --disable-libssp --disable-libgomp --disable-decimal-float --disable-libquadmath --disable-libatomic --disable-libcc1 --disable-libmpx --enable-checking=release` | identical | |

**Prerequisites.** `contrib/download_prerequisites` in the 6.5.0 tarball is still the 2010
script: it fetches over `ftp://gcc.gnu.org` (dead) and it names the *minimum* supported
versions, `gmp-4.3.2 mpfr-2.4.2 mpc-0.8.1 isl-0.15`. So the script fetches `gmp-6.1.0`,
`mpfr-3.1.4`, `mpc-1.0.3` and `isl-0.16.1` from `https://gcc.gnu.org/pub/gcc/infrastructure/`
and unpacks them in-tree instead. Section 5 shows experimentally that the choice makes no
difference to the output.

**Patches needed to build GCC 6.5.0 with Debian bullseye's GCC 10.2.1: none.** Not one
source file failed to compile, and the two aborted attempts before the first good build were
my own scripting - a 404 on a prerequisite URL, then the stale symlink of section 5. About
13 minutes on 10 cores. Two notes for the record:

* `-fcommon` was added to the host `CFLAGS`/`CXXFLAGS` pre-emptively, as the standard
  mitigation for GCC 10 defaulting to `-fno-common`. It was never shown to be *needed* -
  GCC's own sources compile as C++, where the tentative-definition problem does not arise -
  and I did not re-run without it. Either way it is a flag for compiling the compiler and
  cannot reach the compiler's output.
* `makeinfo` is not installed, so `make` fell back to the `missing` wrapper and printed
  *"Makeinfo is missing. Info documentation will not be built."* The release tarball ships
  pre-built `.info` files, so `make install` succeeded; only the documentation rebuild was
  skipped.

**Binutils placement.** The new prefix is seeded with a copy of the stock binutils 2.32
*before* configuring, at `$PREFIX/arm-linux-gnueabi/bin/` and `$PREFIX/bin/`. That matters
twice: GCC's configure runs its `gcc_cv_as_*` feature probes against whichever target
assembler it can find, and it finds this one at exactly the canonical location Arnd's build
would have used (he installs binutils into the prefix first); and it makes the new prefix a
drop-in PATH replacement for the kernel build, which calls `arm-linux-gnueabi-ld`,
`-objcopy`, `-nm` and friends directly. Afterwards `arm-linux-gnueabi-gcc
-print-prog-name=as` resolves to
`$PREFIX/lib/gcc/arm-linux-gnueabi/6.5.0/../../../../arm-linux-gnueabi/bin/as` - the copied
2.32.

**First-look sanity checks**, new compiler against stock:

| probe | stock | ours |
|---|---|---|
| `--version` | `arm-linux-gnueabi-gcc (GCC) 6.5.0` | `arm-linux-gnueabi-gcc (arm_multilib_uclibc_20200924) 6.5.0` |
| `-v` banner | `gcc version 6.5.0 (GCC)` | `gcc version 6.5.0 (arm_multilib_uclibc_20200924)` - **the sibling camera's kernel banner, verbatim** |
| `.comment` of `int x;` | `GCC: (GNU) 6.5.0` | `GCC: (arm_multilib_uclibc_20200924) 6.5.0` - **the shipped string, verbatim** |
| `md5sum` of `-dumpspecs` | `f4d4b8fd08111cac916cf0c2cafa0649` | `f4d4b8fd08111cac916cf0c2cafa0649` |
| `-print-multi-lib` | `.;` | `.;` |
| `libgcc.a` | 16,581,626 B, 1,751 members | 16,577,510 B, **the same 1,751 members** |

Identical built-in specs is a strong early signal: the specs string is exactly where a
differently configured GCC shows its differences.

`libgcc.a` is the one place the two prefixes hold genuinely different bytes, and it is worth
saying why it does not matter. Taking one member, `_udivsi3.o`, the difference is the ident
string plus the DWARF strings that record where the compiler was built:

```
stock  DW_AT_name /home/arnd/git/gcc/libgcc/config/arm/lib1funcs.S
       DW_AT_comp_dir /home/arnd/git/buildall/aarch64-linux-gnu-arm/gcc/arm-linux-gnueabi/libgcc
       DW_AT_producer GNU AS 2.32
ours   DW_AT_name ../../../gcc-6.5.0/libgcc/config/arm/lib1funcs.S
       DW_AT_comp_dir /build/gcc-vendor/build/arm-linux-gnueabi/libgcc
       DW_AT_producer GNU AS 2.32
```

Build-directory paths, and the same assembler on both sides. A kernel module is `ld -r`,
never linked against `libgcc`, so none of it can reach our output anyway.

## 4. Verification: the pkgversion changed the pkgversion and nothing else

Method: two complete builds of the module from the same tree, in the same vendor build path
(`build/build-vendorpath.sh`), against the same vendor kernel, with the same pinned
`__DATE__`/`__TIME__`. The only difference between the runs is `TOOLCHAIN_BIN`.

**The control reproduces the recorded baseline exactly** - 1,890,660 bytes, structural
37,630, raw 1,228,291, `.comment` 9,347. That also establishes that the build is
deterministic run to run, and that nothing else drifted while this work package was open.

### 4.1 Object level: 158 / 158 byte-identical

The module compiles to 158 object files: 156 driver objects, the `ld -r` merge `8188fu.o`,
and `8188fu.mod.o`. (156 + `8188fu.mod.o` = the 157 `.ident` copies in `.comment`;
`8188fu.o` already contains the other 156.) Compared pairwise between the two builds:

* **all 158 differ** when compared raw - the expected consequence of a longer `.ident`;
* **all 158 are byte-identical** after `arm-linux-gnueabi-objcopy --remove-section=.comment`;
* and, so as not to rest on objcopy being a fair transformation, an independent ELF32 reader
  compared every section-header field (type, flags, size, link, info, align, entsize) and a
  SHA-256 of every section's contents, skipping only `.comment`: **158 objects compared, 0
  differ.** That covers `.text`, `.data`, `.rodata*`, `.bss`, every `.rel*` section,
  `.symtab`, `.strtab`, `.ARM.exidx` and `.ARM.attributes`.

This is stronger than the check the work package asked for. It is not "the 1,293
known-identical functions stayed identical"; it is "every byte of every object file other
than the ident string is the same".

### 4.2 `.text` level: `offsetdiff.py` unchanged

| | stock | vendor-pkgversion |
|---|---:|---:|
| same-size functions | 3886 | 3886 |
| semantically identical | **3882 (98.6%)**, 949,220 B (97.3% of `.text`) | **3882 (98.6%)**, 949,220 B |
| same size but differing | 4 | 4 |
| differing words | 6 same-opcode + 1 different-opcode | 6 same-opcode + 1 different-opcode |
| which functions | `collect_bss_info` (4), `rtw_efuse_map_write` (1), `rtw_BT_efuse_map_write` (1), `rtw_wx_set_priv` (1) | identical list, identical counts |

No regression, and no improvement - as expected, since `.text` never sees the string.

### 4.3 Whole file: `fulldiff.py`

| section | before | after |
|---|---:|---:|
| `.text` | 9,692 | 9,692 |
| **`.comment`** | **9,347** | **84** |
| `.rel.text` | 7,688 | 7,688 |
| `.rodata.str1.1` | 3,493 | 3,493 |
| `.symtab` | 3,020 | 3,020 |
| `.strtab` | 1,288 | 1,288 |
| `.data` / `.bss` / `.rodata` | 956 / 671 / 420 | 956 / 671 / 420 |
| `.rel.ARM.exidx` / `.ARM.exidx` / `.rel.rodata` | 408 / 372 / 256 | 408 / 372 / 256 |
| `.note.gnu.build-id` | 19 | 20 |
| **STRUCTURAL total** | **37,630 (1.962%)** | **28,368 (1.479%)** |
| RAW | 1,228,291 (64.04%) | 1,221,637 (63.69%) |
| module size | 1,890,660 | 1,894,584 |
| byte-identical sections | 16 / 41 | 16 / 41 |

Every line except `.comment` and the build-id is unchanged to the byte. `.note.gnu.build-id`
is an SHA-1 over the linked module, so 19 differing bytes out of 20 becoming 20 is noise; it
converges only when everything else does.

### 4.4 `.comment` itself

| | shipped | before | after |
|---|---:|---:|---:|
| section size | 6,837 | 2,826 | 6,751 |
| copies | 159 | 157 | 157 |
| bytes per copy | 43 | 18 | 43 |
| string | `GCC: (arm_multilib_uclibc_20200924) 6.5.0` | `GCC: (GNU) 6.5.0` | `GCC: (arm_multilib_uclibc_20200924) 6.5.0` |

`ld -r` does not merge this section, so it is a plain concatenation of one `\0<ident>\0` run
per input object. **Our `.comment` is now a byte-exact prefix of the shipped one**, and the
entire remainder of the shipped section is

```
\0GCC: (arm_multilib_uclibc_20200924) 6.5.0\0\0GCC: (arm_multilib_uclibc_20200924) 6.5.0\0
```

- two more copies, 86 raw bytes, one per object file we do not have. That is an independent
confirmation, from a section that has nothing to do with code, that the OEM contribution is
**exactly two translation units**, which is what `FINDINGS-byte-gap.md` deduced separately
from the symbol table and from the extra out-of-line `copy_*_user` bodies.

(`fulldiff.py` scores this as 84 rather than 86 because it keys `.comment` content by string
rather than by run, counting 42 bytes per copy and leaving the two separator NULs to the raw
column, which does say 86.)

## 5. An accidental control: the prerequisite libraries do not matter

The first successful build picked up `gmp-4.3.2` and `mpfr-2.4.2` - the ancient minimums -
because a symlink left behind by an aborted earlier run shadowed the versions the script
meant to fetch. The bug is fixed (the guard now tests the versioned directory and re-points
the symlink with `ln -sfn`; `ln -sf x gmp` on an existing symlink-to-directory creates
`gmp/x` rather than replacing it, which is how it survived), and GCC was rebuilt from
scratch with the intended `gmp-6.1.0` / `mpfr-3.1.4` / `mpc-1.0.3` / `isl-0.16.1`.

The driver was then built a third time, with that second compiler. Its 158 object files are
byte-identical to the first compiler's, **and so is the linked `8188fu.ko`, all 1,894,584
bytes of it including the build-id hash**. GMP 4.3.2 + MPFR 2.4.2 and GMP 6.1.0 + MPFR 3.1.4
produce the same ARM code.

That is the expected answer - GMP is exact integer arithmetic, MPFR is correctly rounded, so
neither is version-sensitive for constant folding, and ISL is only consulted for
`-floop-*`/Graphite, which `-Os` never enables - but it is now measured rather than assumed.
It also disposes of the "did you use the same support libraries Arnd did?" objection, since
two different answers demonstrably give the same compiler output. As a side effect it shows
the whole module build is bit-reproducible end to end.

## 6. Is the vendor's GCC stock? (time-boxed)

Searched: OpenIPC's `firmware` tree, Buildroot's GCC 6.5.0 package, crosstool-NG's samples,
and the open web for the pkgversion string and for a published Fullhan SDK toolchain.

* **OpenIPC does not use the vendor toolchain.** Its Fullhan support
  (`br-ext-chip-fullhan/`, nine `fh88xx_lite_defconfig`s including `fh8856v200`) builds its
  own Buildroot toolchain: `BR2_TOOLCHAIN_BUILDROOT_MUSL=y`, `BR2_GCC_VERSION_13_X=y`,
  `BR2_TOOLCHAIN_BUILDROOT_VENDOR="openipc"`. musl and GCC 13 - nothing to do with
  `arm_multilib_uclibc_20200924`. Clean negative.
* **No Fullhan SDK dump carrying the toolchain was found.** The public traces of Fullhan
  toolchains are names quoted in third-party SDK READMEs (Tuya's IPC SDK references an
  `arm-fullhanv2-linux-uclibcgnueabi` for the FH8626), not a recipe and not a tarball.
* **The name matches a crosstool-NG sample, but only by shape.** crosstool-NG ships
  `samples/arm-multilib-linux-uclibcgnueabi` with `CT_TARGET_VENDOR="multilib"`,
  `CT_MULTILIB=y`, `CT_CC_GCC_MULTILIB_LIST="aprofile"`, `CT_LIBC_UCLIBC_NG=y`. Read as
  `arm` + `multilib` + `uclibc` + a build date, the vendor's pkgversion looks like that
  sample rebuilt on 2020-09-24 with `CT_TOOLCHAIN_PKGVERSION` set to the directory name.
  Suggestive; not evidence.
* **Had it been Buildroot instead**, the era's `package/gcc/6.5.0/` carries 13 patches, of
  which only two could touch ARM code generation at all: `830-arm_unbreak_armv4t.patch`
  (changes an armv4t default that an explicit `-march=armv7-a` overrides anyway) and
  `831-ARM-PR-target-70473-Reduce-size-of-Cortex-A8-automat.patch` (an upstream rewrite of
  the Cortex-A8 scheduling automaton). The rest are m68k, xtensa, microblaze, MIPS, uclinux
  and libgcc.

**Verdict: the recipe is not published, and on the evidence it is Hikvision-internal** (the
sibling camera's CI hostname, section 1). The question is nearly moot - but it is worth
being precise about *why*, because the reasoning is not what section 4 measured.

Section 4 compares *our* rebuilt GCC against the *stock kernel.org* GCC. It proves that
adding `--with-pkgversion` perturbs nothing, which is what this work package had to
establish. It says nothing directly about the vendor's compiler.

What speaks to the vendor's compiler is the module itself, and it has already spoken:
**3,882 of 3,939 functions - 97.3% of `.text` - are instruction-for-instruction identical
between the shipped module and a build made with a stock FSF GCC 6.5.0**, and not one
load/store immediate differs anywhere in the module. The 57 that are not identical are all
accounted for: 46 absent OEM functions, four `__LINE__` constants that measure the OEM
patch, four call sites into OEM code, and the three residuals in `FINDINGS-byte-gap.md`. A
compiler carrying backported ARM patches would not land on that. So whatever recipe
assembled `arm_multilib_uclibc_20200924`, on this code at `-Os` for ARMv7 it behaves as
stock GCC 6.5.0, and any residual difference had nowhere left to hide - at the end of this
work package the OEM sources were the only thing between the rebuild and a byte-exact file,
and closing them is what produced one.

## 7. Re-running

```sh
docker exec fuv sh /src/build/build-gcc-vendor.sh     # ~13 min, installs to /opt/gcc-6.5.0-vendor
docker exec fuv sh /src/build/build-vendorpath.sh     # uses it by default
python3 build/fulldiff.py /path/to/original/8188fu.ko ./8188fu.ko --brief
python3 build/offsetdiff.py /path/to/original/8188fu.ko ./8188fu.ko

# control build with the stock kernel.org crosstool compiler:
docker exec fuv sh -c 'TOOLCHAIN_BIN=/opt/gcc-6.5.0-nolibc/arm-linux-gnueabi/bin \
                       sh /src/build/build-vendorpath.sh'
```

The compiler itself is not committed - 91 MB of binaries - and neither are the GCC sources.
`build/build-gcc-vendor.sh` rebuilds it from published tarballs in one command.
