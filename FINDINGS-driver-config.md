# Barrier 3: the driver's own `#ifdef` configuration

> **Status: closed**, and the module now reproduces byte for byte. This note is
> the record of the work package that recovered the configuration; its numbers
> are that pass's, not the current state. `README.md` §3.3 lists the settings as
> they now stand and §4 has the final accounting.

WP-C asked for one number: the `#ifdef` that makes `sizeof(struct mlme_priv)` equal 4168
instead of our 2856. It is **`CONFIG_APPEND_VENDOR_IE_ENABLE`**, and it is exact - not
approximately 1312, but 1312 to the byte, with the four independently derived offsets
(`mlmeextpriv`, `iopriv`, `registrypriv`, `HalData`) all landing on their targets at once.

Chasing the rest of the configuration from the two modules' symbol tables turned up four
more flags. Together they take the rebuild from **2570 to 3882 semantically identical
functions (65.2% -> 98.6%)**, and remove *every* struct-layout difference from the
histogram: `offsetdiff.py` now reports zero `ldst` immediate mismatches across the whole
module. What is left is 46 OEM functions with no public source, four functions whose only
difference is a `__LINE__` constant, and two single-function oddities described at the end.

## 1. `struct mlme_priv`, member by member

`include/rtw_mlme.h:592-865`. Twenty conditional blocks, plus the members whose size comes
from a compile-time constant. The status column is what the *current* build actually
defines, read out of the preprocessor (`gcc -dM -E` with the driver's own flags) rather
than assumed from the Makefile - several of these are set in `include/autoconf.h` or
`include/drv_conf.h` and never appear as a `-D` on the command line.

| guard | members | status | note |
|---|---|---|---|
| `CONFIG_LAYER2_ROAMING` | `to_roam`, `roam_network`, `roam_*`, `last_roaming`, `clnt_auth_lock` | ON | `-D` from Makefile |
| `CONFIG_CONCURRENT_MODE && CONFIG_AP_MODE` | `candidate_network` | off | |
| `CONFIG_BCN_CNT_CONFIRM_HDL` | `new_beacon_keys`, `new_beacon_cnts` | off | |
| `CONFIG_ARP_KEEP_ALIVE` | `bGetGateway`, `gw_mac_addr`, `gw_ip` | off | |
| `CONFIG_SET_SCAN_DENY_TIMER` | `set_scan_deny_timer`, `set_scan_deny` | ON | via `drv_conf.h` |
| `CONFIG_ACTIVE_TPC_REPORT` | `active_tpc_report` | ON | via `drv_conf.h` |
| `CONFIG_80211N_HT` | `num_sta_no_ht`, `num_FortyMHzIntolerant`, `htpriv` (72 B) | ON | via `autoconf.h` |
| `CONFIG_80211AC_VHT` | `vhtpriv` | off | 8188F is 11n-only |
| `ROKU_PRIVATE` | `vhtpriv_infra_ap`, `htpriv_infra_ap` | off | |
| `CONFIG_RTW_80211R` | `ft_roam` (556 B), `auth_rsp`, `auth_rsp_len` | ON | |
| `CONFIG_RTW_WNM \|\| CONFIG_RTW_80211K` | `nb_info` (328 B), `ch_cnt` | ON | both on |
| `CONFIG_AP_MODE && CONFIG_NATIVEAP_MLME` | `num_sta_*`, `olbc*`, `ht_op_mode`, the `wps_*`/`p2p_*` IE pointers, `bcn_update_lock`, `ap_isolate` | ON | |
| `CONFIG_WFD && CONFIG_IOCTL_CFG80211` | `wfd_*_ie`, `wfd_*_ie_len` | ON | `CONFIG_WFD` via `autoconf.h` |
| `CONFIG_RTW_MBO` | `pcell_data_cap_ie`, `cell_data_cap_len`, `mbo_attr` (208 B) | ON | |
| `RTK_DMP_PLATFORM` | `Linkup_workitem`, `Linkdown_workitem` | off | does not even compile |
| `RTW_BUSY_DENY_SCAN` | `lastscantime` | ON | unconditional in `drv_conf.h:28` |
| `CONFIG_CONCURRENT_MODE` | `scanning_via_buddy_intf` | off | |
| **`CONFIG_APPEND_VENDOR_IE_ENABLE`** | **`vendor_ie_mask[5]`, `vendor_ie[5][255]`, `vendor_ielen[5]`** | **was off, now ON** | **+1312** |
| `CONFIG_RTW_MULTI_AP` | `unassoc_sta_*`, two `_queue`s | off | |
| `CONFIG_PLATFORM_CMAP_INTFS` | `cmap_unassoc_sta[]` | off | inside MULTI_AP |

Size-bearing constants: `cur_network` is a `struct wlan_network` (1064 B) embedding
`WLAN_BSSID_EX` (928 B) with `IEs[MAX_IE_SZ]`, `MAX_IE_SZ = 768`
(`include/wlan_bssdef.h:19`). `MAX_IE_SZ` is a **dead end** as a suspect, and provably so:
the same `WLAN_BSSID_EX` is embedded in `struct mlme_ext_priv`'s `mlmext_info`, so growing
it would shift `iopriv` by *twice* the growth. The measured shift is exactly once, so
whatever grew is unique to `mlme_priv`.

### The sweep

`build/szprobe/` compiles one `char` array per `sizeof()` using the driver's own include
path and `EXTRA_CFLAGS` (lifted verbatim from `core/.rtw_mlme.o.cmd`, so it tracks the
Makefile automatically) and reads the answers back out of the ELF symbol sizes. It takes
about a second, so every candidate can be tried:

```
sh build/szprobe/run.sh -UCONFIG_APPEND_VENDOR_IE_ENABLE [-D<candidate>]
```

| flag added to the baseline | `sizeof(struct mlme_priv)` |
|---|---:|
| *(none - the old build)* | 2856 |
| **`CONFIG_APPEND_VENDOR_IE_ENABLE`** | **4168** |
| `CONFIG_CONCURRENT_MODE` | 3920 |
| `CONFIG_80211AC_VHT` | 2936 |
| `CONFIG_BCN_CNT_CONFIRM_HDL` | 2928 |
| `CONFIG_RTW_MULTI_AP` | 2888 |
| `ROKU_PRIVATE` | 2880 |
| `CONFIG_ARP_KEEP_ALIVE` | 2864 |
| `CONFIG_RTW_MESH` | 2864 |
| `CONFIG_SET_SCAN_DENY_TIMER` / `CONFIG_ACTIVE_TPC_REPORT` / `CONFIG_WFD` | 2856 (already on) |
| `CONFIG_BEAMFORMING` | 2856 (no member in this struct) |
| `RTK_DMP_PLATFORM` | does not compile |

One candidate hits the target, and it hits it exactly.

### Why 1312 and not 1316

The block itself is 1316 bytes, so the arithmetic is worth spelling out - it was the one
thing that did not add up on paper before the probe was built. Measured offsets:

```
mbo_attr        2640  + sizeof(struct mbo_attr_info) 208  ->  2848
lastscantime    2848  (u32, RTW_BUSY_DENY_SCAN)           ->  2852
__alignof__(struct mlme_priv) == 8
   without the block: last byte 2852, rounded up to        2856
   with the block:
     vendor_ie_mask[5]   u32 at 2852                       ->  2872
     vendor_ie[5][255]   u8  at 2872 (1275 B)              ->  4147
     (1 byte of padding to re-align u32)                   ->  4148
     vendor_ielen[5]     u32 at 4148                       ->  4168, no tail padding
```

The block is 1316 bytes but it swallows the 4 bytes of tail padding the struct already
had, so `sizeof` grows by **1312**. That is the number the whole histogram was made of.

Consequences, all confirmed by the probe against the values recovered from the binary:

| | our old build | **now** | shipped (from the binary) |
|---|---:|---:|---:|
| `sizeof(struct mlme_priv)` | 2856 | **4168** | 4168 |
| `offsetof(_ADAPTER, mlmeextpriv)` | 2880 | **4192** | 4192 |
| `offsetof(_ADAPTER, iopriv)` | 5728 | **7040** | 7040 |
| `offsetof(_ADAPTER, registrypriv)` | 12408 | **13720** | 13720 |
| `offsetof(_ADAPTER, HalData)` | 15088 | **16400** | 16400 |

## 2. What the symbol tables said about the rest of the configuration

Both modules are unstripped, so the `FUNC` symbol sets can simply be subtracted. Before
this work: 67 symbols only in the shipped module, 52 only in ours.

### Functions the shipped module has and we did not build

Of the 67, 46 are OEM code that is not in the Realtek tarball (`ez_*`, `rtw_ezviz_ie_set`,
`woal_is_*_country`, `set_smartconfig_flag`, `check_probe_sync_*`, `process_config_vars`,
`hexdump`, ...) - that is WP-D and was expected. Eleven more were `*.constprop.N` /
`*.part.N` clones whose numeric suffix differed only because the OEM files shift GCC's
counters. That leaves nine real ones, in two groups:

| group | functions | implies |
|---|---|---|
| vendor IE | `rtw_build_vendor_ie`, `rtw_vendor_ie_set`, `rtw_vendor_ie_set_api`, `rtw_vendor_ie_get`, `rtw_vendor_ie_get_api`, `rtw_vendor_ie_get_data`, `rtw_vendor_ie_get_raw_data` | `CONFIG_APPEND_VENDOR_IE_ENABLE = y` |
| platform hooks | `platform_wifi_power_on`, `platform_wifi_power_off` | `CONFIG_PLATFORM_OPS` **not** defined |

The vendor-IE group is worth dwelling on: the brief listed `rtw_vendor_ie_*` among the OEM
functions with no public source. That is wrong. All seven are in the Realtek tarball
(`core/rtw_mlme_ext.c:3391`, `os_dep/linux/ioctl_linux.c:8291` onwards), guarded by
`CONFIG_APPEND_VENDOR_IE_ENABLE` - the very flag that owns the 1312 bytes. The symbol-set
oracle and the struct-size oracle independently pointed at the same switch.

The platform hooks are a trap of our own making. `platform/platform_ops.c` defines the two
default stubs inside `#ifndef CONFIG_PLATFORM_OPS`; the macro is a *suppression* switch
that a real platform file sets to say "I provide these myself". The reproduction Makefile's
`CONFIG_PLATFORM_GENERIC_ARM` block was defining it while still compiling `platform_ops.o`,
so nothing defined them at all and the two symbols vanished. `CONFIG_PLATFORM_OPS` has
exactly two occurrences in the whole source tree, both in that one file's guard.

### Functions we built that the shipped module does not have

Forty of the 52 are one family:

```
LPS_Enter LPS_Leave LPS_Leave_check PS_RDY_CHECK lps_ctrl_wk_hdl rtw_exec_lps
rtw_lps_ctrl_wk_cmd rtw_lps_ctrl_leave_set_level_cmd rtw_lps_change_dtim_hdl
rtw_lps_rfon_ctrl rtw_set_lps_lclk rtw_dm_in_lps_hdl rtw_dm_in_lps_wk_cmd
_ips_enter _ips_leave ips_enter ips_leave ips_netdrv_open rtw_ips_pwr_down
rtw_ips_pwr_up rtw_set_ps_mode rtw_set_rpwm rtw_cpwm_polling cpwm_int_hdl
cpwm_event_callback dma_event_callback proc_get_ps_info proc_set_ps_info
rtw_{register,unregister}_{cmd,evt,rx,tx,task}_alive  tpt_mode_default
```

That is `CONFIG_POWER_SAVING`. The `.rodata` cross-check is unusually clean here, because
`core/rtw_pwrctrl.c` mixes guarded and unguarded code in one file:

| string | enclosing guard | in shipped? |
|---|---|---|
| `%s: Driver Already Leave LPS` (`rtw_pwrctrl.c:1543`) | *(top level)* | yes |
| `%s: IPS_mode=%d, LPS_mode=%d, LPS_level=%d` (`:2406`) | *(top level)* | yes |
| `### PS params=>  power_mgnt(%x)...` (`rtl8188f_hal_init.c:3836`) | *(top level)* | yes |
| `%s(): FW LPS mode = %d, SmartPS=%d, dtim=%d` (`rtl8188f_cmd.c:175`) | *(top level)* | yes |
| `==>ips_enter cnts:%d` (`rtw_pwrctrl.c:89`) | `#ifdef CONFIG_IPS` | **no** |
| `It can't execute LPS without Wi-Fi connection!` (`:974`) | `#ifdef CONFIG_LPS` | **no** |
| `change DTIM from %d to %d, ...` (`rtw_cmd.c:3040`) | `#ifdef CONFIG_LPS` | **no** |
| `%s: back to original LPS/IPS Mode` (`rtw_debug.c:6208`) | `CONFIG_PROC_DEBUG` / `CONFIG_POWER_SAVING` | **no** |

Every unguarded string survives in the shipped module and every guarded one is absent.
The split is perfect, which is what makes this a proof rather than a guess.

Two derivation traps had to be checked before believing it, since both would silently
re-enable `CONFIG_LPS` behind `CONFIG_POWER_SAVING = n`:

* `include/autoconf.h:235` - `#ifdef CONFIG_BT_COEXIST` `#define CONFIG_LPS`. Harmless
  here: `CONFIG_BT_COEXIST = n` already. (The README's "enabled per the object list"
  paragraph claims BT_COEXIST is on; it is not, and that line is now stale.)
* `include/drv_conf.h:792` - `#ifdef DBG_CONFIG_ERROR_RESET` `#define CONFIG_IPS`.
  Harmless: `DBG_CONFIG_ERROR_RESET` at `autoconf.h:298` is inside a block comment.

Verified after the change with `gcc -dM -E`: `CONFIG_POWER_SAVING`, `CONFIG_LPS` and
`CONFIG_IPS` are all undefined in the rebuilt driver.

The remaining twelve of the 52 were `*.constprop.N` suffix collisions. After the rebuild
the *ours-only* set is **empty** and every `constprop`/`part` suffix number matches the
shipped module exactly - GCC's clone counters only line up if the same functions were
compiled in the same order from the same set of translation units.

### `OBJECT` symbols

Same treatment, as a second channel. 1839 shipped vs 1802 ours. Every name-level difference
is OEM (`ez_mac_addr`, `ez_new_sc`, `*_country_code_table`, `smart_flg`, `scan_flag`,
`probe_req_t`, ...); nothing is ours-only. The only size mismatch on a named global is
`rtw_rates`, and that is an artefact of two distinct file-scope `rtw_rates` arrays (48 and
144 bytes) existing in both modules and the join pairing them crosswise.

### Undefined (kernel) symbols

205 shipped vs 201 ours; four extra in the shipped module. Three of them - `kmalloc_caches`,
`kmem_cache_alloc`, `kernel_read` - are referenced *only* from OEM functions
(`ez_get_mac_addr`, `ez_wifi_preinit`, `ez_os_get_image_block`), so they say nothing about
configuration. The fourth, `__alloc_skb`, is discussed in section 6.

## 3. Two more flags, found from what was left over

With the symbol sets equalised, `offsetdiff.py` still showed 41 differing words in
`loadparam` and two in `dump_drv_cfg`.

`loadparam` copies the module parameters into `registry_priv`. The differing words are
`ldr`s from two literal-pool base pointers, and both pool words carry the *same* addend in
both modules (`.data+1576` and `.bss+21872`), so the bases are identical and the plus/minus 4
shifts are real layout. Walking the `.data`/`.bss` symbol maps in that window gives the
answer in one line: the shipped module has `rtw_tx_pwr_lmt_enable` in **`.data`** at +2008;
we have it in **`.bss`**. It is declared

```c
int rtw_tx_pwr_lmt_enable = CONFIG_TXPWR_LIMIT_EN;   /* os_intfs.c:836, #if CONFIG_TXPWR_LIMIT */
```

so a zero initialiser puts it in `.bss` and a non-zero one in `.data`; everything after it
in each section slides by four. Reading the shipped module's `.data` at that offset gives
the value directly: **1**. `CONFIG_TXPWR_LIMIT_EN = y`. That also fixed `dump_drv_cfg`,
whose two differing words were `mov r3, #0` against `mov r3, #1` - the same constant being
printed.

The last size mismatch that was not OEM-related was `phy_SpurCalibration_8188F`: ours 1184
bytes, shipped 964. `hal/rtl8188f/rtl8188f_phycfg.c` guards fourteen
`odm_set_bb_reg(pDM_Odm, 0xC40, ...)` calls with `#ifndef CONFIG_AUTO_NOTCH_FILTER` (and
adds two under `#ifdef`). Fourteen four-argument calls at roughly 16 bytes each is ~224,
against a measured 220. `CONFIG_AUTO_NOTCH_FILTER` is **referenced in that one file and
defined nowhere in the tarball** - there is no Makefile switch for it - so the vendor
passed it by hand. Defining it makes the function byte-identical.

## 4. Changes made

All in `Makefile`; the kernel tree and its `.config` were not touched.

| change | evidence |
|---|---|
| `CONFIG_APPEND_VENDOR_IE_ENABLE = n` -> `y` | `sizeof(struct mlme_priv)` 2856 -> 4168, and seven `rtw_vendor_ie_*` / `rtw_build_vendor_ie` symbols the shipped module has |
| `CONFIG_POWER_SAVING = y` -> `n` | 40 LPS/IPS functions we built that the shipped module lacks; every `CONFIG_LPS`/`CONFIG_IPS`-guarded string absent from the shipped `.rodata` while every unguarded one is present |
| drop `-DCONFIG_PLATFORM_OPS` from the `CONFIG_PLATFORM_GENERIC_ARM` block | it is the `#ifndef` guard around the `platform_wifi_power_on`/`_off` stubs, which the shipped module contains |
| `CONFIG_TXPWR_LIMIT_EN = n` -> `y` | `rtw_tx_pwr_lmt_enable` lives in `.data` with value 1 in the shipped module, in `.bss` in ours |
| new `CONFIG_AUTO_NOTCH_FILTER = y` (not a stock Realtek switch) | `phy_SpurCalibration_8188F` 1184 -> 964 bytes, matching exactly |
| `REALTEK_CONFIG_PATH` `/lib/firmware/` -> `/dav/` (via a new `USER_CONFIG_PATH ?=` override, matching the existing `USER_EFUSE_MAP_PATH` pattern) | the shipped `rtw_phy_file_path` relocation resolves to the string `/dav/`; `/lib/firmware/` does not occur anywhere in the shipped module |

`EFUSE_MAP_PATH` (`/system/etc/wifi/wifi_efuse_8188fu.map`) and `WIFIMAC_PATH`
(`/data/wifimac.txt`) were checked the same way and already match.

## 5. Measurements

`python3 build/offsetdiff.py <shipped> ./8188fu.ko`, against the same Fullhan vendor kernel
throughout - the only variable is the driver configuration.

| | stock kernel (WP-A) | vendor kernel (WP-B) | **+ driver config (WP-C)** | shipped |
|---|---:|---:|---:|---:|
| same-size functions | 3038 | 3497 | **3886** | (3939 distinct) |
| **semantically identical** | 2197 (55.8%) | 2570 (65.2%) | **3882 (98.6%)** | |
| identical bytes of `.text` | 365,924 (37.5%) | 423,356 (43.4%) | **949,220 (97.3%)** | |
| distinct `FUNC` symbols | | 3872 | **3893** | 3939 |
| symbols only in shipped | | 67 | **46** (all OEM) | |
| symbols only in ours | | 52 | **0** | |
| `.text` | 1,005,464 | 972,784 | **966,132** | 975,780 |
| module | 1,953,988 | 1,904,016 | **1,890,468** | 1,918,056 |

Section-level shortfall, all of it consistent with the 46 missing OEM functions:

| section | shipped | ours | delta |
|---|---:|---:|---:|
| `.text` | 975,780 | 966,132 | -9,648 |
| `.rodata` | 36,824 | 36,404 | -420 |
| `.rodata.str1.1` | 196,583 | 192,890 | -3,693 |
| `.data` | 46,976 | 46,020 | -956 |
| `.bss` | 28,498 | 27,827 | -671 |
| `.init.text` | 252 | 252 | 0 |
| **`.modinfo`** | **9,246** | **9,246** | **byte-identical** |

`.modinfo` matching to the byte is its own small proof: it carries `vermagic`, `version`,
`alias`, and the full list of module parameters with their types and descriptions. A
module-parameter set that agrees exactly is hard to reach by accident.

The offset histogram - the thing this work package existed to empty - is now empty. Not one
`ldst` immediate differs anywhere in the module.

## 6. What is left, honestly

**Forty-six OEM functions (WP-D).** `ez_*` (34), `woal_is_*_country` (7), plus
`rtw_ezviz_ie_set`, `set_smartconfig_flag`, `set_scan_flag`, `check_scan_flag`,
`check_sn_valid`, `check_probe_sync_EID`, `check_probe_sync_eid208`, `process_config_vars`,
`hexdump`. Roughly 9.6 KB of `.text`. No public source; reconstruction from
`8188fu.ko.c` is a separate work package.

**Three functions distorted by OEM call sites**, also WP-D: `OnProbeReq` (-176 bytes,
missing `ez_probe_req_handler` / `ez_probe_requst_eid208_handler`), `OnProbeRsp` (-12),
`rtw_ioctl` (-332, missing the `ez_*_ioctl_handle` cases). `rtw_usb_primary_adapter_init`
(-8) is the same thing in miniature: the shipped version calls `ez_wifi_preinit` between
`_rtw_zvmalloc` and `loadparam`, and is otherwise instruction-for-instruction identical.

**Four functions differing only in a `__LINE__` constant**, which is the OEM patch measured
from the other side:

| function | file | our `__LINE__` | shipped | delta |
|---|---|---:|---:|---:|
| `collect_bss_info` | `core/rtw_mlme_ext.c` | 10521 | 10582 | +61 |
| `rtw_wx_set_priv` | `os_dep/linux/ioctl_linux.c` | 7838 | 7840 | +2 |
| `rtw_efuse_map_write` | `core/efuse/rtw_efuse.c` | 2875 | 2876 | +1 |
| `rtw_BT_efuse_map_write` | `core/efuse/rtw_efuse.c` | 3024 | 3025 | +1 |

Our line 10521 is the `RTW_INFO("%s()-%d: IE too long...", __FUNCTION__, __LINE__, len)`
inside `collect_bss_info`; the two efuse constants come from that file's local
`RT_ASSERT_RET(expr)` macro, which prints `__FILE__`, `__FUNCTION__` and `__LINE__`. So the
vendor's `rtw_mlme_ext.c` carries 61 more lines above `collect_bss_info` than the tarball
does, `ioctl_linux.c` two more above `rtw_wx_set_priv`, and `rtw_efuse.c` one more above
both efuse writers. These four are exact line-count constraints on the OEM patch and should
be treated as targets when WP-D reconstructs it.

**`_rtw_skb_alloc` - unresolved.** Shipped 156 bytes, ours 64. The source is one line,
`__dev_alloc_skb(sz, in_interrupt() ? GFP_ATOMIC : GFP_KERNEL)`. Ours tail-calls
`__netdev_alloc_skb(NULL, sz, gfp)`, which is what 4.9's `skbuff.h` expands to. The shipped
module instead has an inlined fast path:

```
    cmp   r0, #1024
    bhi   slow                       @ -> b __netdev_alloc_skb(NULL, len, gfp)
    add   r0, r0, #64                @ NET_SKB_PAD
    bl    __alloc_skb                @ (len+64, gfp, SKB_ALLOC_RX=2, NUMA_NO_NODE=-1)
    ...   skb->data += 64; skb->tail += 64; skb->dev = NULL
```

That is `__netdev_alloc_skb`'s `__alloc_skb` branch open-coded behind a `len <= 1024`
guard, and it is the sole reason the shipped module has an extra `__alloc_skb` undefined
symbol. It cannot be produced by any `#ifdef` in the tarball. Two candidates, and the
evidence does not separate them:

* a patched `include/linux/skbuff.h` in the real FH865x BSP. Against this: the FH885xV200
  tree we build with has a `skbuff.h` **byte-identical to stock 4.9.129**, and 1024 is not
  `SKB_WITH_OVERHEAD(PAGE_SIZE)` under any plausible `skb_shared_info` size, so it is not a
  constant that fell out of a config change;
* an OEM patch to `os_dep/osdep_service.c`. The vendor demonstrably patched at least four
  other driver files, and a small-RX-skb fast path is a natural thing for an IP-camera
  vendor to add.

One function, 92 bytes. Recorded rather than guessed at.

**`rtw_efuse_analyze` - unresolved**, 4 bytes. Every branch target inside the function
matches; the shipped version keeps two values in `r7`/`r8` across a `printk` where ours
reloads one from the literal pool, so ours is one instruction longer. A register-allocation
difference this local usually traces to `-fmerge-constants` behaving differently because the
string pool differs - and the string pool differs because the OEM strings are missing. Most
likely it resolves itself when WP-D lands; not worth chasing before then.

**`rtw_sptime_get` is not a difference at all**, recorded so nobody re-investigates it.
Shipped 104 bytes, ours 100, but the two are instruction-for-instruction identical: the
shipped symbol simply includes one extra `.word 0` of padding before its literal pool,
because the function lands at a different address once 9.6 KB of OEM code is absent.
`offsetdiff.py` scores it as a size mismatch; there is nothing to fix.

**Build path (WP-E).** The shipped `.rodata` still carries
`/data1/jiangqifeng6/work/tongyibianyi/develop_branch/wifi/rtl8188FU_linux_v5.15.3-6-g1a2e952f9.20230217/core/efuse/rtw_efuse.c`
and the same for `core/monitor/rtw_radiotap.c`, from `__FILE__` inside `RT_ASSERT_RET`
and `WARN_ON`. We emit
`/src/core/...`. Unchanged by this work, and trivial once someone builds under that path.

## Reproducing

```sh
# the size oracle (needs one prior build so core/.rtw_mlme.o.cmd exists)
docker exec fuv sh /src/build/szprobe/run.sh
docker exec fuv sh /src/build/szprobe/run.sh -UCONFIG_APPEND_VENDOR_IE_ENABLE

# full rebuild + measurement
docker exec fuv sh /src/build/build.sh
python3 build/offsetdiff.py /path/to/original/8188fu.ko ./8188fu.ko --pairs 30
```

`offsetdiff.py` now also prints, after the histogram, the list of same-size functions that
still differ and how many words each one differs by - which is what turned the last three
flags up.
