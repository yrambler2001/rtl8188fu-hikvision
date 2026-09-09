# The OEM code: `ez_sc.c` and `ez_wifi_config.c`

Everything the shipped `8188fu.ko` contains that no public Realtek release does.
This note is the catalogue WP-D was asked for: what the two missing translation
units are, what is in them, how each fact was read out of the binary, and where
the reconstruction stands.

**Result so far:** the whole-file gap went **28,368 -> 1,421 bytes** of
positional difference (1.479% -> **0.07%** of 1,918,056; 228 by the
scoreboard's shift-tolerant structural count, which understates - see section
10). **35 of the 41 sections are byte-identical** -
`.rodata.str1.1`, `.rodata`, `.data`, `.bss`, `.comment`, `.modinfo`,
`.ARM.exidx`, the ARM attributes, **`.strtab`** and eleven of the twelve
relocation sections - every relocation in the module now matches - and
`.symtab` has the right size, the right entry count, no missing or extra
symbol and the right symbol *order*, uniquifiers included.
**43 of the 46 OEM functions are byte-identical**, and so are all four public
functions the OEM patch distorts, plus `rtw_efuse_analyze` (section 14).
Sections 10 to 19 are the current state; sections 1 to 9 are the original WP-D
catalogue.

---

## 0. Time-boxed attempt to just obtain the source - negative

GPLv2 obliges Hikvision to offer this, so it was worth ~20 tool calls before
reconstructing anything. All of it came back empty:

* **`opensource.hikvision.com`** was enumerated programmatically: 14 categories
  (`/Home/List?id=10,11,12,16,18,42,43,45,46,47,48,49,50,51`), every page of
  each, **131 model rows total**. Every row has `N/A` in both the *License* and
  *Source* columns - the portal publishes no packages at all, only an inquiry
  form. Not one row matches `ezviz|CS-C|wifi|Wi-Fi|8188|realtek|IPC|FH88|FH86|fullhan`.
  There is no FH865X / Fullhan / EZVIZ entry to find.
* **GitHub / code search**: `grep.app` is behind a bot check and `searchcode.com`'s
  API is gone; web search for `rtw_ezviz_ie_set`, `ez_wifi_preinit`,
  `set_smartconfig_flag`, `ez_sc.c`, `ez_wifi_config.c` and
  `rtl8188FU_linux_v5.15.3` returns only the usual public rtl8188fu forks, none
  of which contain any `ez_*` symbol.
* **`Ezviz-Open`, `EZVIZ-OpenSource`, `OpenIPC/device-ezviz`** carry SDKs and
  firmware, no GPL driver drop.
* The **`woal_is_*_country` lead is a dead end as a donor.** The prefix really is
  Marvell's (`woal_` = the mlan/moal wireless OS abstraction layer), but none of
  the reachable Marvell/NXP trees define these functions: checked
  `StreamUnlimited/marvell-sd-uapsta-8987` (`moal_main.c`, `moal_cfg80211.c`,
  `moal_sta_cfg80211.c`), `balena-os/linux-artik7` (sd8977) and
  `nxp-imx/mwifiex` (`mxm_wifiex`). They have `woal_is_any_interface_active`,
  `woal_is_connected`, `woal_is_valid_alpha2` - never `woal_is_etsi_country` and
  friends. The EZVIZ author borrowed the naming convention, not the code.

**Conclusion: the source is not publicly available.** Everything below is read
out of the binary.

---

## 1. The two files, and which function belongs to which

`ld -r` keeps one `STT_FILE` symbol per input object and groups that object's
**local** symbols under it. Diffing the shipped file list against ours gives
exactly two extras and no missing ones:

```
shipped STT_FILE count 159, ours 157
shipped-only: ez_sc.c, ez_wifi_config.c
ours-only:    (none)
```

GCC's `.file` directive carries `lbasename(main_input_filename)`, so these are
basenames and the **order of the 159 `STT_FILE` entries is the link order**. The
two OEM objects sit at index 75 and 76, between `rtw_rhashtable.c` (74) and
`hal_intf.c` (77) - i.e. appended to `_OS_INTFS_FILES` in the Makefile, right
after `os_dep/linux/rtw_rhashtable.o`. That is where the reconstruction puts
them, and it reproduces the shipped symbol and section ordering.

The locals grouped under each `STT_FILE` (including the ARM `$a`/`$d` mapping
symbols) give each object's exact byte ranges:

| | `.text` | `.rodata` | `.data` | `.bss` |
|---|---|---|---|---|
| `ez_sc.c` | `0x92220-0x9311c` | `0x6ecc-0x6f99` | `0x1674-0x1679` | `0x5b70-0x5dfe` |
| `ez_wifi_config.c` | `0x9311c-0x94568` | `0x6f99-0x706d` | `0x1679-0x1a2d` | `0x5dfe-0x5e0f` |

Both objects also carry their own out-of-line `copy_from_user` / `copy_to_user`
bodies (GCC emits one per translation unit that needs them): `ez_sc.c` has both
(`0x92220`, `0x92298`), `ez_wifi_config.c` has `copy_to_user` (`0x9311c`). Those
three are the "extra `copy_*_user` copies" `FINDINGS-byte-gap.md` counted, and
they appear automatically once the two files exist.

**Split: `ez_sc.c` 18 functions (3,836 bytes), `ez_wifi_config.c` 28 functions
(4,900 bytes).** All 46 are `GLOBAL` - the vendor declared nothing `static`.

### `.text` order is *not* source order

GCC 4.9+ emits functions in reverse postorder of the call graph so callees are
compiled before callers, and `-Os` does not change that. The `__func__.NNNN`
uniquifier is a `DECL_UID`, assigned in *parse* order, so the two orders can be
compared - and they differ:

```
ez_wifi_config.c   .text order          __func__ UID
  ez_set_country                        75918/75919
  ez_read_rssi_per_ant_ioctl            75954
  ez_get_mac_addr                       76004
  ez_wifi_preinit                       75935/75936   <-- out of order
```

So in the vendor's source `ez_wifi_preinit` is defined between `ez_set_country`
and `ez_read_rssi_per_ant_ioctl`, but GCC emitted it after `ez_get_mac_addr`
because it calls both. Same in `ez_sc.c`: `check_probe_sync_EID` has the lowest
UID (70989) yet lands 13th in `.text`. This matters only for the `.NNNN` digits
in `.strtab`; those are already byte-identical, so the reconstruction's source
order is close enough that GCC's renumbering lands on the same values.

---

## 2. The 46 functions

`.text` order; sizes are the shipped `st_size`. `S` = byte-identical in the
current reconstruction; the `S` column is as of the original WP-D pass
(37/46) - it is 42/46 now, see section 10. Callees and referenced objects come from
`build/oem/oemdiff.py --catalogue`, which resolves every relocation, including
section-relative addends into `.rodata.str1.1`.

### `ez_sc.c` - smart config and device discovery over probe frames

| S | addr | size | function | what it does |
|---|---|---:|---|---|
| y | 92220 | 120 | *(local)* `copy_from_user` | per-TU out-of-line copy |
| y | 92298 | 88 | *(local)* `copy_to_user` | per-TU out-of-line copy |
| y | 922f0 | 16 | `ez_set_join_fail_reason` | `err_status = result` |
| y | 92300 | 16 | `ez_get_join_fail_reason` | returns it, sign-extended (`ldrsb`) |
| y | 92310 | 20 | `set_smartconfig_flag` | `smart_flg = flag` |
| y | 92324 | 16 | `check_scan_flag` | returns `scan_flag` (zero-extended) |
| y | 92334 | 28 | `set_scan_flag` | `scan_flag = !!flag` |
| y | 92350 | 116 | `hexdump` | `printk` a buffer, newline every 16 bytes. Nothing calls it. |
| n | 923c4 | 436 | `ez_set_new_sc` | the `EZ_NEW_SMART_CONFIG_IO` sub-command switch (INIT/DEINIT/POLL/GET/SET_REASON) |
| n | 92578 | 56 | `ez_new_sc_ioctl` | null check, tail-calls `ez_set_new_sc` |
| y | 925b0 | 400 | `rtw_ezviz_ie_set` | the tail of the public `rtw_vendor_ie_set()` with the group hardcoded to 0 |
| y | 92740 | 232 | `ez_new_sc_ioctl_handle` | copies <=512 user bytes into `ez_new_sc.buf`, publishes them as a probe-req vendor IE, kicks a scan |
| n | 92828 | 276 | `ez_device_info_ioctl_handle` | copies a 9-byte serial + model string into `DeviceInfo` |
| y | 9293c | 44 | `check_sn_valid` | `memcmp(DeviceInfo, null_sn, 9) != 0` |
| y | 92968 | 244 | `check_probe_sync_EID` | walks IEs looking for EID 207 (or 209 when the serial is set) carrying `"EZVIZ"` |
| y | 92a5c | 116 | `ez_probe_req_handler` | on a hit, copies the IE payload into `ez_new_sc` and sets `done` |
| y | 92ad0 | 160 | `check_probe_sync_eid208` | byte-walks the frame for EID 208 + `"EZVIZ"` (a **stack** copy of the literal, `strlen()`d at run time) |
| y | 92b70 | 260 | `ez_probe_response_eid208_handler` | on a hit, snapshots the 42-byte element into `probe_resp_t` and traces it |
| n | 92c74 | 408 | `ez_probe_requst_eid208_handler` | same, plus: if the payload's first 9 bytes are our serial, bump `id` 0x6990->0x6991, or 0x6992->0x6993 while appending a 4-byte `{0x6994, len 1, err_status}` TLV |
| n | 92e0c | 784 | `ez_scan_device_ioctl_handle` | the `EZ_IOCTL_SCAN_IO` sub-command switch (IDLE / TRIG_SCAN_DEVICE / POLL_DEVICE / TRIG_SCAN_REASON / POLL_REASON) |

### `ez_wifi_config.c` - per-unit configuration, efuse, version

| S | addr | size | function | what it does |
|---|---|---:|---|---|
| y | 9311c | 88 | *(local)* `copy_to_user` | per-TU out-of-line copy |
| n | 93174 | 344 | `process_config_vars` | a small `key=value` scanner over the config file: skips `#` comments, `\` continuations and duplicate spaces, returns the picked value's length |
| y | 932cc | 72 | `ez_os_get_image_block` | `kernel_read` wrapper (see the bug in section 6) |
| y | 93314 | 52 | `ez_os_open_image` | `filp_open(name, O_RDONLY, 0)`, `IS_ERR` -> NULL |
| y | 93348 | 16 | `ez_os_close_image` | `filp_close(fp, NULL)` |
| y | 93358 | 92 | `woal_is_us_country` | 7-entry table |
| y | 933b4 | 92 | `woal_is_br_country` | 27 entries |
| y | 93410 | 96 | `woal_is_etsi_country` | 118 entries |
| y | 93470 | 92 | `woal_is_eu_country` | 36 entries |
| y | 934cc | 92 | `woal_is_apec_country` | 81 entries |
| y | 93528 | 60 | `woal_is_jp_country` | 1 entry |
| y | 93564 | 92 | `woal_is_other_country` | 46 entries |
| y | 935c0 | 236 | `ez_set_country` | US->`rtw_channel_plan=0x43`, EU->`0x42`, JP->`0x37`, else `0x62`. **Only three of the seven tables are consulted** - `br`/`etsi`/`apec`/`other` are dead. |
| y | 936ac | 96 | `ez_wifi_version_info` | prints platform `M377`, chip `rtl8188s`, version `-SN215081-Release_231225`, and its own `__DATE__`/`__TIME__` = `Dec 25 2023 20:43:30` |
| y | 9370c | 276 | `ez_read_rssi_per_ant_ioctl` | returns `{valid, rssi_a-100, rssi_a-100, recvpriv.rssi}` from `pHalData->odmpriv` |
| y | 93820 | 64 | `ez_hexval` | one hex digit |
| y | 93860 | 68 | `ez_atox` | hex string -> int |
| n | 938a4 | 156 | `ez_strsep` | `strsep`-alike with `:` separator and `/` escape |
| n | 93940 | 148 | `ez_mac2u8` | `"aa:bb:.."` -> 6 bytes. **Nothing calls it.** |
| y | 939d4 | 596 | `ez_get_mac_addr` | reads `/home/config.txt`, picks `mac_addr=`, needs exactly 17 chars, points `rtw_initmac` at `ez_mac_addr` |
| y | 93c28 | 644 | `ez_wifi_preinit` | reads the same file, picks `ccode=`, needs exactly 2 chars, calls `ez_set_country`, then version info and `ez_get_mac_addr`. Called from `rtw_usb_primary_adapter_init`. |
| y | 93eac | 28 | `ez_GetMaskBit` | returns the constant `0x9F` |
| y | 93ec8 | 364 | `ez_GetWiFiVersion` | maps that mask to `0.0.0_`/`1.0.0_`/`1.0.1_`/`1.0.2_`/`1.0.3_` + the release string |
| n | 94034 | 216 | `ez_wifi_func_poll_ioctl_handle` | copies that version string out to user space |
| y | 9410c | 136 | `ez_read_efuse` | `rtw_efuse_mask_map_read` wrapper |
| y | 94194 | 280 | `ez_read_efuse_mac` | 6 bytes at efuse 0xD7, rejects all-`ff` and all-`00` |
| y | 942ac | 344 | `ez_read_efuse_rf` | 12 bytes at 0x10 (none may be `0xff`), plus 0xB9 crystal calibration and 0xBA thermal meter |
| y | 94404 | 120 | `ez_read_eFuse_free_block` | `efuse_GetMaxSize - efuse_GetCurrentSize` |
| y | 9447c | 236 | `ez_wifi_module_rf_calibration_check_ioctl` | returns 0/1/2/3 for mac/rf failures, 4 if the efuse is full |

Undefined symbols only the OEM code needs, and which functions need them:
`kernel_read` (`ez_os_get_image_block`), `kmalloc_caches` + `kmem_cache_alloc`
(the constant-size `kmalloc()`s in `ez_get_mac_addr` / `ez_wifi_preinit`), and
`__alloc_skb` (which turned out to belong to `_rtw_skb_alloc`, section 7).

---

## 3. The OEM-owned data

Sizes and addresses are the shipped symbol table's; contents were read straight
out of `.data` / `.rodata`.

`ez_sc.c`:

| sym | sec | size | contents |
|---|---|---:|---|
| `err_status` | `.bss` | 1 | **LOCAL** (static). The `.bss` anchor GCC uses for the whole file. |
| `smart_flg` | `.bss` | 1 | |
| `scan_flag` | `.bss` | 1 | |
| `ez_new_sc` | `.bss` | 516 | `{u8 enable; u8 done; u8 buf[512]; u16 len;}` - the `+514` halfword is read with `ldrh`, the two flags with `ldrb` at `+0`/`+1` |
| `DeviceInfo` | `.bss` | 41 | 9-byte serial + 32-byte model |
| `null_sn` | `.bss` | 9 | all zero, the "serial not set" comparand |
| `probe_resp_t` | `.bss` | 42 | `struct ez_probe_t` |
| `probe_req_t` | `.bss` | 42 | `struct ez_probe_t` |
| `ez_sync_code` | `.data` | 5 | `"EZVIZ"`, no NUL - **LOCAL** |

`struct ez_probe_t` is 42 bytes and **packed**: `element` at 0, `element_len` at
1, `sync[5]` at 2, `u16 id` at **7** (unaligned - the shipped code reads it with
a plain `ldrh`, which is legal because ARMv7 builds enable `-munaligned-access`,
and writes it as two `strb`), `len` at 9, `value[32]` at 10.

`ez_wifi_config.c`:

| sym | sec | size | contents |
|---|---|---:|---|
| `us_country_code_table` | `.data` | 21 | LOCAL, `"US\0CA\0MX\0TW\0VI\0DO\0GT"` |
| `br_country_code_table` | `.data` | 81 | LOCAL, 27 codes |
| `etsi_country_code_table` | `.data` | 354 | LOCAL, 118 codes |
| `eu_country_code_table` | `.data` | 108 | LOCAL, 36 codes |
| `apec_country_code_table` | `.data` | 243 | LOCAL, 81 codes |
| `jp_country_code_table` | `.data` | 3 | LOCAL, `"JP"` |
| `other_country_code_table` | `.data` | 138 | LOCAL, 46 codes |
| `ez_mac_addr` | `.bss` | 17 | the `"xx:xx:xx:xx:xx:xx"` string `rtw_initmac` ends up pointing at |
| `invalid_efuse_data1` | `.rodata` | 10 | ten `0xff` |
| `invalid_efuse_data2` | `.rodata` | 10 | ten `0x00` |

The tables are **flat `char[]` with a 3-byte stride**, not `char[][3]`: the
loops walk a byte index `i += 3` and stop at `i != sizeof(table)`. Writing them
as 2-D arrays compiles to the same data but a different loop, and that was worth
6 of the 46 functions.

19 `__func__` / `__FUNCTION__` constants live in `.rodata` and identify which
functions log their own name and with which spelling - both are used, sometimes
in the same function (`ez_set_country` and `ez_wifi_preinit` each have one of
each), so the spelling has to be reproduced literally.

---

## 4. The 115 OEM strings

`build/fulldiff.py --strings` reported 115 strings (3,493 bytes) present only in
the shipped `.rodata.str1.1`; they are now all reproduced and that section is
byte-identical. In offset order they fall into six clumps, which is itself
evidence of source order:

* **35621** `rtw_vendor_ie_set,ret:%d!!!\n` - inside `core/rtw_mlme_ext.c`'s
  strings, i.e. emitted by `OnProbeReq`, not by the OEM files.
* **93441-93558** `EZ_NEW_SMART_CONFIG_IO \n`, `EZ_IOCTL_SET_NEW_SC \n`,
  `EZ_IOCTL_SCAN_IO \n`, `EZ_IOCTL_DEVINFO_IO \n`,
  `EZ_IOCTL_READ_RSSI_PER_ANT \n`, `EZ_IOCTL_WIFI_FUNC_POLL \n` - inside
  `os_dep/linux/ioctl_linux.c`'s strings, i.e. `rtw_ioctl`'s dispatch.
* **113160-114490** `ez_sc.c`, in `.text` order: the hexdump banners, the five
  `cmd NEW_SC_*` traces, the six duplicated `[%s] ... append vendor ie` messages
  `rtw_ezviz_ie_set` inherits from `rtw_vendor_ie_set`, the device-info traces,
  the two `get ez_sync_code` messages, `GET AP DTAT SUCCESS`, a second copy of
  the literal `EZVIZ`, and the scan-device traces.
* **114491-115037** the country tables' `found region code=%s in ... table`
  messages, `ez_set_country`'s three `RTW_ERR`s, and
  `ez_wifi_version_info`'s `M377` / `rtl8188s` / `-SN215081-Release_231225` /
  **`20:43:30`** / **`Dec 25 2023`** - the second build timestamp.
* **115038-115866** RSSI, config-file and MAC-address messages.
* **115867-116482** the five version prefixes and the efuse messages.

The eight strings that appear **twice** in the shipped module (`CN`, `EZVIZ`,
`%s%sRTW: %s: rtw_efuse_mask_map_read error!`, and five `append vendor ie`
messages) are exactly the literals the OEM files duplicate from public files -
`ld -r` does not merge across input objects, so a second copy proves a second
translation unit uses the same literal.

---

## 5. The OEM call sites in public code

Found by scanning every `.text` relocation whose target is an OEM symbol and
attributing it to the function that owns the offset. There are exactly four such
functions, and this is the complete list of insertions:

| function | file | offset | what is inserted |
|---|---|---:|---|
| `rtw_usb_primary_adapter_init` | `os_dep/linux/usb_intf.c` | +24 | `ez_wifi_preinit();` between the `rtw_zvmalloc` NULL check and `loadparam()` |
| `OnProbeReq` | `core/rtw_mlme_ext.c` | +336, +348, +384, +516 | a block just before the `_SSID_IE_` `rtw_get_ie()`: the smart-config sniffer, the EID-208 request handler, and either publishing `probe_resp_t` as a probe-response vendor IE or clearing it |
| `OnProbeRsp` | `core/rtw_mlme_ext.c` | +276 | `ez_probe_response_eid208_handler(pframe, precv_frame->u.hdr.len);` immediately before the `mlmeext_chk_scan_state(SCAN_PROCESS)` test |
| `rtw_ioctl` | `os_dep/linux/ioctl_linux.c` | +84..+340 | seven private ioctls |

Two shapes had to be recovered, not guessed:

* **`rtw_ioctl` is an if/else-if chain, not switch cases.** The shipped module
  tests `0x8BF5, 0x8C05, 0x8C08, 0x8C07, 0x8BFB, 0x8C09, 0x8C0B` linearly with
  `movw`/`cmp`/`bne` and only then enters the balanced decision tree GCC builds
  for the Realtek cases. Putting them inside the `switch` merges them into that
  tree and changes 1,088 bytes.
* **`OnProbeReq`'s guard is a bitwise `&`.** The shipped code is
  `clz r3,r3; lsr r3,r3,#5; movls r3,#0` - GCC if-converting
  `(ez_new_sc.done == 0) & ((len - WLAN_HDR_A3_LEN) > 255)`. With `&&`, or with
  the operands the other way round, GCC branches instead.

The guard on the two mode-dependent ioctls reads `dev->ieee80211_ptr->iftype`
(offset 468 in this kernel's `struct net_device`, `iftype` at +4 in
`struct wireless_dev`, probed with the `szprobe` technique): `NL80211_IFTYPE_AP`
(3) for `EZ_NEW_SMART_CONFIG_IO`, `NL80211_IFTYPE_STATION` (2) for the other
two; otherwise `ret = EINVAL` - positive 22, which is what the binary returns.

### `__LINE__` reconciliation

Three files carry `__LINE__` constants that pin how many lines the vendor added
above a given point (`FINDINGS-driver-config.md`):

| file | constrained function | shipped `__LINE__` | delta |
|---|---|---:|---:|
| `core/rtw_mlme_ext.c` | `collect_bss_info` | 10582 | +60 |
| `os_dep/linux/ioctl_linux.c` | `rtw_wx_set_priv` | 7840 | +2 |
| `core/efuse/rtw_efuse.c` | `rtw_efuse_map_write`, `rtw_BT_efuse_map_write` | 2876, 3025 | +1 |

(The `rtw_mlme_ext.c` delta is 60, not the 61 `FINDINGS-driver-config.md`
records: `__LINE__` inside the multi-line `RTW_INFO` invocation evaluates one
higher than the line its text starts on.)

The recovered `OnProbeReq`/`OnProbeRsp` code accounts for 21 of those 60 lines,
and all three functions now compile byte-identically, so the *code* the vendor
added above `collect_bss_info` is fully accounted for. The other 39 lines
emitted nothing - comments, blank lines, a different wrapping style, or edits in
a block this configuration compiles out - and the binary cannot say which. They
are reproduced as a labelled comment block at the top of the file, which is the
whole of their observable effect; `core/rtw_mlme_ext.c` says so at the point it
does it. The same applies to the +2 and +1 in the other two files.

---

## 6. Vendor bugs that have to be reproduced

Three of the byte-identical functions are only byte-identical because the
reconstruction repeats a mistake:

1. **`ez_os_get_image_block` calls `kernel_read` with 4.14 argument order
   against 4.9's prototype.** 4.9 declares
   `int kernel_read(struct file *, loff_t, char *, unsigned long)`; the vendor
   writes `kernel_read(fp, buffer, size, &fp->f_pos)` (the 4.14+ signature). GCC
   warns and converts: the buffer pointer is **sign-extended into the `loff_t`
   offset** (`mov r2,r0; asr r3,r0,#31`), the size is passed as the address, and
   `&fp->f_pos` as the count. Writing the call correctly does not reproduce the
   function.
2. **`ez_wifi_preinit` frees NULL.** Under an `if (pick != NULL)` guard it emits
   `mov r0,#0; bl kfree` - so the 1 KB parse buffer leaks on every probe.
3. **`ez_set_country` never consults four of its seven tables.** `br`, `etsi`,
   `apec` and `other` are built, exported and dead; only US/EU/JP are tested.

---

## 7. `_rtw_skb_alloc` - residual closed

`FINDINGS-byte-gap.md` section 4.1 left two observationally-equivalent
hypotheses for the 92-byte `_rtw_skb_alloc` difference: a patched
`__dev_alloc_skb` inline in the vendor's `skbuff.h`, or an OEM patch to
`os_dep/osdep_service.c`. **It is the driver patch.** Section 4.1's
reconstruction, dropped into `os_dep/osdep_service.c` behind `CONFIG_EZ_WIFI`
and compiled against the same unmodified vendor kernel headers, reproduces the
shipped function exactly:

```c
if (sz <= 1024) {
        skb = __alloc_skb(sz + NET_SKB_PAD,
                          in_interrupt() ? GFP_ATOMIC : GFP_KERNEL,
                          SKB_ALLOC_RX, NUMA_NO_NODE);
        if (skb) { skb_reserve(skb, NET_SKB_PAD); skb->dev = NULL; }
        return skb;
}
return __dev_alloc_skb(sz, in_interrupt() ? GFP_ATOMIC : GFP_KERNEL);
```

The one detail that mattered beyond section 4.1's text: the `in_interrupt()`
ternary is written out at **both** call sites rather than hoisted into a `gfp_t`
local - the shipped code CSEs the `preempt_count` load but selects the mask
twice.

`rtw_sptime_get`'s 4-byte difference also disappeared on its own, as section 4.3
predicted: it was a literal-pool alignment `nop` that depends on where the
function lands once 9.6 KB of OEM code is present.

---

## 8. What GCC 6.5.0 at `-Os` taught us

Recurring rules the reconstruction had to learn. Each of these was worth
multiple functions:

* **`||` operands come out reversed.** `if (!dev || !rq)` emits
  `cmp rq; cmpne dev`. `&&` does not reverse. (Where the vendor wrote which
  order is therefore readable off the binary, and it is not consistent between
  functions.)
* **Error paths land out of line only when they are the `else`.** Guard-clause
  early returns (`if (bad) { log; return; } ... work ...`) put the error block
  in the fall-through; `if (good) { work } else { log; return; }` puts it after,
  which is what the shipped module has everywhere.
* **`if (a && b) { if (!ptr) {...} } else {...}` then the body** is the exact
  shape of the three ioctl entry sequences: it produces `beq` to a cold block
  placed between the inner error block and the main body.
* **GCC 6.5 refuses to fold `strcpy` at `-Os`** (`gimple_fold_builtin_strcpy`
  bails unless the length is zero when `optimize_size`), so
  `ez_GetWiFiVersion`'s inline 6-byte + 25-byte copies must be written as
  `memcpy`, and each `switch` arm must carry its own copy of both.
* **`char version[32] = {0};` is a `memset` call; `memset(v,0,32)` is
  `__memzero`** - ARM's `asm/string.h` macro rewrites the latter, and an
  initializer never goes through the macro.
* **Function order in `.text` is reverse postorder of the call graph**, so it
  falls out of the call structure rather than from where you put the functions.

---

## 9. Tooling

`build/oem/` is the loop. It compiles only what changed and scores it, in
seconds, instead of running the 158-file build:

```sh
docker exec fuv sh /src/build/oem/run.sh                     # score all 46 OEM functions
docker exec fuv sh /src/build/oem/run.sh --fn NAME -v        # per-instruction dump
docker exec fuv sh /src/build/oem/pub.sh core/rtw_mlme_ext.c OnProbeReq -v
docker exec fuv sh /src/build/oem/dis.sh 0x92220 0x94570     # annotated shipped disassembly
docker exec fuv sh /src/build/oem/ourdis.sh ez_sc NAME       # our object, one function
docker exec fuv python3 /src/build/oem/align.py NAME        # the two streams, edit-distance aligned
docker exec fuv python3 /src/build/oem/align.py NAME --obj /tmp/ours.ko   # ... against the linked module
docker exec fuv sh /src/build/oem/asm.sh ez_sc               # our assembly, whole unit
docker exec fuv sh /src/build/oem/dump.sh ez_sc -fdump-rtl-ira      # GCC internals
docker exec fuv sh -c 'SRCFILE=/src/build/oem/lab/run1/x.c \
        sh /src/build/oem/dump.sh ez_sc -fdump-tree-all'     # ... of a lab variant
docker exec fuv python3 /src/build/oem/uidgap.py             # the DECL_UID oracle
docker exec fuv sh /src/build/oem/uidat.sh /path/to/any.c    # its uniquifiers
python3 build/oem/oemdiff.py --shipped /path/8188fu.ko --catalogue
```

### The variant search

Hand-guessing C shapes stops paying after a few dozen tries; the last four
residuals took about 27,000 machine-generated ones.  A *spec* expresses one
function as a template with orthogonal, semantically-neutral axes -
declaration order, local types, explicit temporary versus recomputation,
`if/else` versus early return, operand order in commutative expressions,
short-circuit order, loop form, `switch` versus if-chain, cached base pointer
versus repeated dereference, extra locals, statement order where independent -
and the generator splices every combination into a real copy of the unit:

```sh
python3 build/oem/gen.py --spec build/oem/specs/ez_strsep.py --out build/oem/lab/s1
docker exec fuv sh -c 'cd /src && python3 build/oem/lab.py \
        --unit ez_wifi_config --dir build/oem/lab/s1 --fn ez_strsep -j 10'
```

`lab.py` compiles ten at a time and scores each three ways:

* `n` - differing 4-byte words, relocation-aware, from `oemdiff.py`;
* `d` - the size delta;
* `s` - the Levenshtein distance of the two instruction sequences **with the
  register fields blanked out**.

`s` is the one to steer by.  `n` is nearly useless as a gradient: a variant
that is right except for which registers IRA picked scores almost every word
different, and a positional comparison of two sequences that differ by one
inserted instruction scores everything after it different too.  `s` says how
many instructions really differ - `ez_strsep`'s residual is `s=2`, and the
whole search for it was "find a shape below 3".

`align.py` prints the alignment that `s` counts, side by side, with the
relocations and branch targets resolved:

```
 300 03530020 cmpeq                            300 03530020 cmpeq
 304 03a07001 moveq                         <<
 308 13a07000 movne                         <<
 312 0a000003 B .+332                      r  304 0a000002 B .+320
```

`<<` and `>>` are instructions only one side has, `!!` a real substitution,
`r` a word that differs only in its register fields.  It takes an object or the
linked module, so it is also the way to check a function *in place* rather than
symbolically.

Results are cached by source hash (plus any extra flags, plus a scoring
version), so re-running a sweep after adding variants only compiles the new
ones.  The specs used are in `build/oem/specs/`; `build/oem/lab/` is scratch
and is not tracked.

`oemdiff.py` compares an object file to the linked module, which cannot be done
positionally: bytes under a relocation are masked and compared symbolically
instead (target symbol, addend, and for `.rodata.str1.1` the actual string),
B/BL words by their resolved callee, intra-function branches by their offset
from the function start, and GCC's `.NNNN` uniquifier is stripped from symbol
names. `annot.py` resolves literal-pool addends so the shipped code is readable.

---

## 10. Where this stands, and what is left

`python3 build/fulldiff.py <shipped> ./8188fu.ko --brief`, and a plain
positional byte comparison of the two files:

| | bytes | share of file |
|---|---:|---|
| before WP-D | 28,368 | 1.479% |
| after WP-D | 972 | 0.051% |
| after the first residual pass | 1,421 | 0.074% |
| after the `.text` order fix (section 20) | 141 | 0.007% |
| after the process_config_vars pass | 121 | 0.0063% |
| **now** (`ez_strsep` closed, section 18) | **116** | **0.0060%** |

| section | raw bytes differing | what it is |
|---|---:|---|
| `.text` | 96 | content in two functions; the section is the right *length*, every symbol is at the right *address* and has the right size |
| `.note.gnu.build-id` | 20 | an SHA-1 of the module; converges last, by construction |
| everything else | **0** | |

**39 of the 41 sections are byte-identical** - `.rodata`, `.rodata.str1.1`,
`.data`, `.bss`, `.symtab`, `.strtab`, `.modinfo`, `.comment`, all twelve
relocation sections and all four exidx sections.  All 879 `__func__.NNNN`
uniquifiers match, every one of the 3,909 function symbols has the shipped
`st_size` *and the shipped `st_value`*, and every one of the 38,970
relocations matches.  `.text` is exactly 975,780 bytes.

### Read the raw number, not the structural one

`fulldiff.py` has two counts and they measure different things.  The
**structural** one matches symbols by name and charges a function whose size is
wrong only its size *delta*, so one moved function cannot inflate it into the
hundreds of thousands - but it therefore rates a 344-byte function that should
be 340 at 4 bytes and a 344-byte function with 176 differing bytes at 176.  The
**raw** one is a plain positional `cmp`.  Compare attempts by the raw number.

The same warning applies one level down.  `oemdiff.py` compares an *object* to
the linked module, which cannot be done positionally, so it masks every word
under a relocation and every `B`/`BL` displacement and compares those
symbolically.  That is what makes it usable at all - but it means a function it
calls byte-identical can still differ in the linked output, and for four
functions it did: see section 20.  When `run.sh` says 46/46, check the linked
module too.

### Closed during this pass

| | was | now | how |
|---|---|---|---|
| `.text` order of the four probe / EID208 handlers | 873 bytes in `.text`, 208 in `.rodata.str1.1`, 161 in `.rel.text`, 13 in `.ARM.exidx`, 17 in `.symtab` | **0** | `ez_probe_req_handler` belongs *before* `check_probe_sync_eid208` in the source.  Section 20 |
| `process_config_vars` | 98 bytes, edit distance 12 | 79 bytes, edit distance 5 | the guard is `(pos \| n) \| (pos & n)`, the `n` test's arms write `pos = n`, and `end` is declared before `j`.  Section 17 |

### The two that remain

**44 of the 46 OEM functions are byte-identical**, and so are all four public
functions the OEM patch distorts.  Both that remain are the *right size*
and at the right address; what differs is which register the allocator picked.

| function | differs by | what is known |
|---|---:|---|
| `process_config_vars` | 79 bytes, 44 words, edit distance 5 | Two mechanisms, both named exactly.  The guard temp is coalesced into pos's partition, because `uncprop` rewrites all seven main-path `pos = 0` PHI arguments into it and out-of-SSA's coalesce costs *accumulate per edge*, so seven beats `pos_6`'s two - that costs a `b`, a `mov` and a latch `mov`.  And the shipped build materialises `m` with a dead `moveq #1` / `movne #0` pair where ours branches straight to the shared `m = 1`.  Section 17 |
| `ez_new_sc_ioctl` | 17 bytes, 5 words, edit distance 2 | One IRA decision, now traced to its input: the colouring order comes from `bucket_allocno_compare_func`, whose first key is `ALLOCNO_FREQ`, which at `-Os` is exactly 1000 x the number of RTL references.  `rq` has three and `is_null` two, so `rq` is coloured first and its weight-125 shuffle preference sends it to r2.  Two more references on `is_null` reverse the order and the function is byte-identical.  Section 21 |

### Next steps, in the order worth doing them

1. `ez_new_sc_ioctl` needs `is_null` to carry more RTL references than `rq`
   (section 21).  The property is exact and the effect is proven; what is
   missing is an ordinary-C construct that adds a reference without adding an
   instruction.  The narrowest remaining hypothesis is the cross-jumped
   duplicate: an `if`/`else` on an already-live value whose two arms are
   character-identical and each end in a conditional, so IRA counts both copies
   and `pass_jump2` - which runs after reload - merges them again.  It needs an
   *existing* conditional to duplicate, and this function has none that VRP
   does not delete.
2. `process_config_vars`: give the guard temp a type that `gimple_can_coalesce_p`
   refuses against pos's (`((int)(pos | n)) | ((int)(pos & n))` with `pos`
   unsigned) and the seven PHI arguments stay constants and the whole register
   cascade comes out right - `orrs r9, r2, r6`, `moveq r2, r6`, `moveq r4, r6`
   all match exactly.  What then goes wrong is *layout*: the seven `pos = 0`
   edge copies become real blocks, cross-jumping merges them with the `n`-test
   arm's own `pos = 0`, and `reorder_basic_blocks_simple` chains the loop tail
   after the arms instead of after the merged copy.  Section 17.
3. `.note.gnu.build-id` will match by itself when the rest does.

---

## 11. `__func__.NNNN`: the DECL_UID oracle

GCC uniquifies file-scope-static and function-local-static symbols by
appending `.` and the declaration's `DECL_UID` - a counter bumped for **every
declaration the front end creates**, headers included.  159 translation units
put 879 such symbols in the shipped module's `.symtab`, and their numbers are
therefore an exact statement about how many declarations each of the vendor's
translation units saw before each function.  Nothing else in the file carries
that information.

`fulldiff.py` scores `.strtab` as 0 because it strips the uniquifiers before
comparing, which is why this went unnoticed: the raw section was **116 bytes
short with 726 symbols renamed**.

Pairing every `.NNNN` symbol between the two modules by section and address
(the `.rodata` those symbols live in is byte-identical, so the pairing is
exact) gave:

```
+54   674 symbols   73 files          <- everything unpatched
-97    83 symbols   ioctl_linux.c
-100   85 symbols   rtw_mlme_ext.c    (+1 at -98)
+52     2 symbols   usb_intf.c        (4 more at +54)
       17 symbols   ez_sc.c, ez_wifi_config.c, spread
```

Reading it:

* **+54 is exactly the cost of the eighteen prototypes in `include/ez_wifi.h`.**
  `drv_types.h` pulls that header into all 159 units, so the vendor's globally
  visible OEM header cannot have carried them.  They moved to
  `include/ez_wifi_fn.h`, included only where the functions are called;
  `hexdump()` (3 UIDs) stays behind, which is what makes the arithmetic land on
  exactly -54.  A prototype costs `1 + max(nparams, 1)` UIDs; an `extern`
  object 1; an enum `n + 1`; a struct `nfields + 1`; a typedef 1.
* **usb_intf.c's split shift** - four symbols at +54, two at +52 - places two
  vendor declarations between `rtw_resume` and
  `rtw_usb_primary_adapter_deinit`.  A local `int ez_wifi_preinit(void);`
  above `rtw_usb_primary_adapter_init` costs exactly 2 and lands exactly there.
  So the vendor declared the OEM entry points locally, at the call site.
* **ioctl_linux.c needs +151 and rtw_mlme_ext.c +152** before their first
  `__func__` (`wpa_set_encryption` and `init_mlme_default_rate_set`), then 2
  more before `OnProbeRsp`.  `ez_wifi_fn.h` with all 46 prototypes plus the
  three ioctl command lists as enums covers 146; the residual 5, and 1 more in
  rtw_mlme_ext.c, are declarations whose definitions were never linked, so only
  their count survives.  They are reproduced as labelled placeholders.

`__LINE__` and `DECL_UID` are independent constraints on the same files, so
every declaration added above a `__LINE__`-constrained point was paid for by
shrinking the line-count reconciliation comments by the same number of lines.

That took the mismatch from 726 symbols to 16, `.strtab` to within 15 bytes of
the shipped size, and `.symtab` from 127 `st_size` mismatches to 2.  The rest
of this section is how the last 16 were closed.

### How the last 16 were closed

The uniquifiers also fix the vendor's **source order**, which `.text` order
cannot (`.text` is reverse postorder of the call graph).  Three functions were
in the wrong place and have been moved: `check_probe_sync_EID` has the lowest
`__func__` UID in ez_sc.c (70989) yet sat thirteenth in the file,
`ez_wifi_preinit` belongs between `ez_set_country` and
`ez_read_rssi_per_ant_ioctl`, and `ez_probe_req_handler` belongs immediately
before `ez_scan_device_ioctl_handle`.

That third move is worth dwelling on, because source order is *not* a free
parameter.  `build/oem/uidgap.py` prints the deficit interval by interval, and
after the first two moves exactly one interval scored **negative** - the span
from `ez_device_info_ioctl_handle`'s `__func__` to `check_probe_sync_eid208`'s
held 21 declarations here and 16 in the vendor's build.  Only two functions in
that span have no `__func__` of their own to pin them, and moving the other
one, `check_sn_valid`, breaks two functions' codegen outright.  Moving
`ez_probe_req_handler` instead leaves every byte-identical OEM function
byte-identical, makes every interval in both files non-negative - and cuts the
raw `.symtab` difference from 7,482 bytes to 3,312, because local symbols are
emitted in source order.  Two independent oracles agreeing is what makes it a
finding rather than a guess.

One declaration came out the same way.  `ez_read_rssi_per_ant_ioctl` cached
four pointers; `build/oem/specs/decl_probe_wc.py` compiles it with each of them
removed in turn and it stays byte-identical every time, so the binary does not
say which the vendor had - but the oracle says it had one fewer, and
`precvpriv` (whose only use was `precvpriv->rssi`) is the one dropped.
`struct ez_rssi_per_ant` moves up to the file-scope declarations for the same
reason: it is five DECL_UIDs, and the interval it was in was one over.

### The 65 that could not be identified, only counted

With source order settled, every interval in both files wanted *more*
declarations than this reconstruction has - 47 across ez_sc.c and 18 across
ez_wifi_config.c:

```
ez_sc.c            interval                             vendor  ours  short
  check_probe_sync_EID -> rtw_ezviz_ie_set                 66    56     10
  -> ez_new_sc_ioctl_handle                                12    11      1
  -> ez_device_info_ioctl_handle                           17    13      4
  -> check_probe_sync_eid208                               16    13      3
  -> ez_probe_response_eid208_handler                      11    10      1
  -> ez_probe_requst_eid208_handler                         9     8      1
  -> ez_scan_device_ioctl_handle                           46    19     27
                                                                     = 47
ez_wifi_config.c
  before ez_set_country                                                 4
  ez_set_country -> ez_wifi_preinit                        16    12      4
  ez_wifi_preinit -> ez_read_rssi_per_ant_ioctl            18    18      0
  -> ez_get_mac_addr                                       50    44      6
  -> ez_wifi_func_poll_ioctl_handle                        34    34      0
  -> ez_read_efuse                                          9     8      1
  -> ez_wifi_module_rf_calibration_check_ioctl             43    40      3
                                                                     = 18
```

The kernel builds with `-Wno-unused-variable` and
`-Wno-unused-but-set-variable`, so unused locals - and `static` helpers that
`-Os` inlines and deletes - cost DECL_UIDs and leave no other trace.  65 such
declarations across two files is entirely ordinary vendor code.  **Which** they
were is not recoverable; **how many**, and **between which two functions**, is
pinned exactly.

So each interval gets one placeholder of exactly that size, named `*_uid_gap_*`
and commented with the interval it stands for.  An `enum` costs one DECL_UID
for the type and one per enumerator, a `typedef` costs one, and neither emits
anything, so the count is all they carry.  The header comment on the first one
in each file says plainly that they are placeholders rather than recovered
vendor code.  This is the treatment `enum ez_unrecovered` in
`include/ez_wifi_fn.h` already had for the five declarations `ioctl_linux.c`
and `rtw_mlme_ext.c` demanded, applied to the rest.

**Result: 879 of 879 uniquified symbols match, `.strtab` is byte-identical
(124,098 bytes), and `.symtab`'s symbol order is identical with the suffixes
rather than only without them.**  `build/oem/uidgap.py` reports 0 short in both
files; delete any one placeholder and every `__func__.NNNN` after it in that
file stops matching.

### The DECL_UID accounting rules

Measured against this exact compiler with `build/oem/uidat.sh`, which prints
the uniquifiers of an arbitrary file, and `-fdump-tree-gimple-uid`, which
prints every declaration's DECL_UID:

| construct | DECL_UIDs |
|---|---:|
| function definition, before its body | `nparams + 2` - the PARM_DECLs first, then the FUNCTION_DECL, then the RESULT_DECL |
| `(void)` parameter list | counts as one parameter; `()` counts as none |
| local variable | 1 |
| `struct`/`union` definition | `nfields + 1` |
| `enum` definition | `nvalues + 1` |
| `typedef` | 1 |
| prototype | `1 + max(nparams, 1)` |
| `for` / `while` loop | 3 - artificial labels, created where the loop *ends* |
| `goto` label | 1, at first mention |
| a definition that follows a prototype | +1 for the merged-away duplicate |
| a definition that follows a tentative definition | +1, likewise |

`__func__` is created at its **first use** inside the function, not at the
function's start, so a `__func__` late in a body counts everything declared
before it.

---

## 12. Block layout at `-Os` is source order, not profile

The single most useful rule learned in this pass.  GCC 6's
`reorder_basic_blocks_simple` sorts candidate edges by frequency **only when
optimising for speed**:

```c
  /* Sort the edges, the most desirable first.  When optimizing for size
     all edges are equally desirable.  */
  if (optimize_function_for_speed_p (cfun))
    std::stable_sort (edges, edges + n, edge_order);
```

At `-Os` the sort never runs, so blocks are chained greedily in **basic-block
order**, which is GIMPLE order, which is source order.  Branch probabilities -
including the very strong `PRED_COLD_FUNCTION` (`PROB_VERY_LIKELY` = 9996/10000)
that the kernel's `__cold` `printk` puts on every error path - are computed and
then ignored.

That makes layout readable off the source and vice versa.  It closed
`ez_wifi_func_poll_ioctl_handle`: the shipped layout is
`[cond][ptr check][iwp error][net error][ret = -1][epilogue][body]`, which
needs the *net* error block to sit between the ptr check and the iwp error
block in GIMPLE order while the ptr check still falls through to the iwp
block - i.e.

```c
	if (dev && rq) {
		if (wrq->u.data.pointer)
			goto ok;
	} else {
		printk("%s():  net or rq == NULL!\n", __func__);
		ret = -1;
		return ret;
	}
	printk("iwp == NULL or iwp->pointer == null!!!\n");
	ret = -1;
	return ret;
ok:
```

Six frequency-changing rewrites of the same code (guard clauses, if/else
chains, `goto`s to a shared exit) had all produced the same wrong layout,
because the frequencies never mattered.

It is also why `ez_strsep`'s escape test has to be written as two `if`s with a
duplicated `memmove` - cross-jumping merges the two copies, and the surviving
one is the earlier, which is what puts the `*p == delim` test after the
`memmove` block.

---

## 13. `uncprop`, and why a `u32` broke `ez_set_new_sc`

`ez_set_new_sc` was 12 bytes short because `ret` lived in `r0` instead of being
coalesced with the switch selector in `r4`.  The cause is a type.

GCC's `uncprop` pass rewrites *constants* in PHI arguments into SSA names that
are known to hold that constant, to save materialising them.  For a `switch` it
records `index == case_value` on every single-valued case edge.  `NEW_SC_INIT`
is 0 and the function's exit PHI has a `0` on that edge, so `uncprop` can
rewrite it to the switch index - but only if the types match, and `ret` is
`int`.  With `u32 sc_cmd[2]` they do not, nothing happens, `ret` gets `r0`,
`NEW_SC_DEINIT` cross-jumps into `NEW_SC_INIT`'s tail and two instructions
vanish.  With `int sc_cmd[2]` the rewrite fires, `ret` coalesces with the
selector, `NEW_SC_INIT` needs no `ret = 0` at all because case 0 already left 0
in `r4`, and the epilogue is `mov r0, r4` - exactly the shipped code.

The same pass is what keeps `process_config_vars` from converging, in the
opposite direction: there it rewrites `n`'s PHI arguments into the `pos | n`
value and shortens `n`'s live range past the calls.

---

## 14. `rtw_efuse_analyze`: the vendor's added line is a brace

`FINDINGS-byte-gap.md` section 4.2 left this as register allocation around a
`printk`.  It is a semantic fix.  Realtek's own source has a brace bug in the
efuse map dump:

```c
	for (i = 0; i < mapLen; i++) {
		if (i % 16 == 0)
			RTW_PRINT_SEL(RTW_DBGDUMP, "0x%03x: ", i);
			_RTW_PRINT_SEL(RTW_DBGDUMP, "%02X%s", ...);
		}
```

so the second print runs every iteration.  The shipped module's control flow
says the vendor's copy does not: at `rtw_efuse_analyze+0x974` it branches on
`i % 16 != 0` straight to the loop increment, past **both** prints, where ours
branched only past the first.  Adding the missing braces reproduces that, and
with the second print now inside the `if` GCC has the registers to keep both
separator strings live across the loop instead of reloading one from the
literal pool - which is the six-instruction window that differed.

The brace also settles the line count: closing it costs exactly one line, which
is the `+1` that `rtw_efuse.c`'s two `__LINE__` constants (2875 -> 2876 and
3024 -> 3025) demanded.  The placeholder comment that stood in for it is gone.

---

## 15. A typedef of `int` is not `int`

Section 13 said `uncprop` is type-sensitive: it rewrites a constant PHI
argument into an SSA name known to hold that constant, but only when the types
match.  This pass found how literally GCC means "match".

`typedef signed int s32;` in `<linux/types.h>` does not make `s32` an alias for
`int` inside the compiler.  `pushdecl` gives every named typedef its own
variant type node so the typedef has a name to print:

```c
      else if (type != error_mark_node && TYPE_NAME (type) != x)
	{
	  type = build_variant_type_copy (type);
	  TYPE_NAME (type) = x;
	  TREE_TYPE (x) = type;
	}
```

`types_compatible_p` still says the two are the same, and
`__builtin_types_compatible_p(s32, int)` is 1 - but `uncprop` compares
`TREE_TYPE` **pointers**, and so does the first test in
`gimple_can_coalesce_p`:

```c
  tree t1 = TREE_TYPE (name1);
  tree t2 = TREE_TYPE (name2);
  if (t1 == t2)
    { check_modes: ... }
```

So `int n` and `s32 n` compile differently.  In `process_config_vars`, with
everything else held fixed, `int pos; int n;` is 352 bytes and `int pos; s32 n;`
is 344 - the shipped size - because the second stops `uncprop` from rewriting
`pos = 0` into the loop guard's `pos | n` value.  (It is not adopted: it costs
more content bytes than the eight it saves in size, and the shape is still not
the shipped one.  See section 17.)

The practical consequence for a reconstruction is that `int`, `s32`, `u32`,
`sint`, `long` and `unsigned long` are six different types for these passes
even where four of them are the same 32-bit signed integer, and the binary can
tell them apart.  `build/oem/specs/process_config_vars_types.py` sweeps the
cross product for exactly this reason.

---

## 16. `ez_scan_device_ioctl_handle`: one literal-pool word - closed

This was the most expensive residual in the file: four bytes of `.text` and
about 192 of the 280 in `.rel.text`.  Section 19 has the fix; this section is
the diagnosis that led to it, and it is worth keeping because the mechanism
recurs.

Both builds put the OEM `.bss` anchor and two addresses derived from it in the
function's literal pool.  Ours puts a third there, `.LANCHOR0+622` - the
address of `probe_req_t.value` - and because the pool is emitted in
first-reference order that word lands in the middle, displacing every entry
after it by four bytes.  Eleven relocations move as a result, and each counts
once as missing and once as extra.

The shipped build never needs the constant:

```
	ldr	r4, .LANCHOR0		@ the anchor
	add	r5, r4, #612		@ &probe_req_t     612 is encodable
	...
	add	r0, r5, #10		@ &probe_req_t.value
```

622 is not an ARM 8-bit-rotated immediate; 612 (`0x99` rotated) and 10 are.

The RTL says both builds start identically.  `-fdump-rtl-expand` for the
memcpy destination:

```
	(set (reg 276) (symbol_ref "*.LANCHOR0"))
	(set (reg 277) (plus (reg 276) (const_int 612)))     ; &probe_req_t
	(set (reg 278) (plus (reg 277) (const_int 10)))      ; &probe_req_t.value
```

and `probe_req_t.id = 0x6990` builds its own `&probe_req_t` the same way,
because the field is an unaligned `u16` in a packed struct and GCC addresses
the two byte stores off it.  Tracking `const_int 622` through the RTL dumps,
it first appears at **`cse_local`** (pass 225): by then the two copies of
`&probe_req_t` - one in the TRIG arm, one in the `if (len)` block - have not
been combined by any global pass, the second has no other use, and folding
`(plus (plus anchor 612) 10)` into the single constant is free.  In the shipped
build they stay one expression, `&probe_req_t` survives into the shared block
(which is why the `id` high byte is stored as `[r5, #8]` rather than
`[r4, #620]`), and `&probe_req_t.value` is an `add`.

Swept without moving it: 180 shapes over cached struct/byte/value pointers and
declaration position, 270 more over those crossed with the copy order and the
`id` spelling, and 105 over the order of the eight field writes.  Every one
scored `d=+4 s=19`.  What moved it was none of those: it was writing the shared
tail out in both TRIG arms instead of jumping to it, which puts the two
`&probe_req_t` in the same basic block.  Section 19.

---

## 17. `process_config_vars`: the guard, the arms, and what is left

Ours is 344 bytes to the shipped 344 and 79 of them differ.  Read off the
shipped disassembly, the register roles are

```
	sl = buf   r8 = i   r5 = j   r2 = pos   r6 = n   r4 = end   r7 = m
	r9 = pos|n   fp = strlen(var)      stack: pick, var, len, &buf[i]
```

and three separate GCC decisions have to come out right.

### 1. `n` has to stay live across the two calls

`n` is in a callee-saved register and the default case - the one with the
`strlen` and `memcmp` calls - never writes it: its value simply survives to the
next iteration.  IRA therefore has twelve allocnos that cross the calls, spills
the three cheapest (`pick`, `var`, `len`), and everything else fits.  If `n` is
instead rematerialised as 0 after the calls IRA has eleven, spills two, keeps
`pick` in `sl`, and splits `pos` across two registers.

Whether `n` survives is decided by VRP.  GCC 6's `register_edge_assert_for`,
for `if (X != 0)` on the edge where `X == 0`, recurses into `X`'s defining
`BIT_IOR_EXPR` and asserts *both* operands zero:

```c
  if (((comp_code == EQ_EXPR && integer_zerop (val))
       || (comp_code == NE_EXPR && integer_onep (val))))
    { ... register_edge_assert_for_1 (op0, EQ_EXPR, e, si);
          register_edge_assert_for_1 (op1, EQ_EXPR, e, si); }
```

so a plain `if (pos | n)` proves `n == 0` on the whole main path, the loop PHI's
`n_9` arguments become the constant 0, and `n` is dead across the calls.

The recursion *one level down*, inside `register_edge_assert_for_1`, is gated
on `has_single_use`:

```c
      if (TREE_CODE (op0) == SSA_NAME && has_single_use (op0))
	register_edge_assert_for_1 (op0, code, e, bsi);
```

`pos` and `n` never have a single use - each is read by the guard, by the
`n` test inside it, and by the loop PHI - so writing the guard as a *nested*
IOR whose two operands are single-use temporaries blocks the whole thing:

```c
	if ((pos | n) | (pos & n)) {
```

`(a | b) | (a & b) == a | b` is a bitwise identity, so this is value-preserving
for *any* operands, not just for two flags that are never both set; and
`combine` folds it back, so the RTL is still one `orrs` compared against zero.  That last part matters twice over,
because it is what lets `cse1` replace `mov rX, #0` on the main path with
`mov rX, r9` - the shipped `moveq r6, r4`, `moveq r4, r9`, `movne r4, r9`.

This is a value-preserving rewrite chosen because it is the only spelling found
that does both.  The vendor's own spelling is not recoverable from the binary;
what *is* recoverable is that their guard was a single `orrs`/`beq` and that
their `n` survived the calls, and this reproduces both.  Ruled out, all
compiled and scored: `(pos | n) == 1` and `(pos | n) > 0` (block the assertion
but need a separate `cmp`); `(int)(pos | n)`, `(s32)(pos | n)`, `(u32)(...)`
and a temporary of another type (the truth-value conversion in
`c_common_truthvalue_conversion` strips a widening `NOP_EXPR`, and TER folds
the temporary into the compare); `(pos | n) & 1`, `& 3`, `& 0xff`,
`pos | (n & 1)`, `% 2`, `<< 0`, `>> 0`, `* 1`, `/ 1`, `+ 0`, `- 0`, `^ 0`,
`!!(pos | n)`, `pos || n`, `n || pos` (VRP's own
`simplify_bit_ops_using_ranges` removes the mask in vrp1 and vrp2 then sees
the bare IOR).

### 2. The `n` test's arms must not merge into the shared `pos = 0`

The shipped guard-true block is

```
	cmp r6, #0 ; moveq r2, r6 ; moveq r4, r6 ; movne r6, #0 ; movne r2, r6 ; b NEXT
```

- both arms clear `pos` *themselves* and branch past the shared `mov r2, #0`.
Writing them as `pos = 0` makes the copies constants, identical to the shared
tail, and cross-jumping merges them.  Writing them as `pos = n` - which is the
same value, because on both arms `n` is the zero - makes them SSA copies, and
an SSA copy is not a constant:

```c
		if (buf[i] == '\n') {
			if (n) {
				n = 0;
				pos = n;
			} else {
				pos = n;
				end = 0;
			}
		}
```

### 3. Declaration order is PHI order is copy order

Out-of-SSA emits one copy per PHI on each incoming edge, in the order the PHIs
sit in the block, and `into_ssa` creates those PHIs in the order the locals are
declared.  That decides which copy is *last* in each arm, and therefore what
cross-jumping can merge.  A 4,320-variant sweep over all 720 declaration
orders crossed with the guard and the arms puts `end` before `j`; it is worth
four words.

### What is left: five instructions

```
  shipped                          ours
  ...
  cmp r7, #32 ; cmpeq r3, #32      cmp r2, #32 ; cmpeq r3, #32
  moveq r7, #1                     -
  movne r7, #0                     -
  beq ZERO_POS                     beq M_ONE
  ...
  mov r7, #1     (m = 1)           mov r9, #1
  -                                b   NEXT
  mov r2, #0     (ZERO_POS)        mov r6, r2
  add r8, r8, #1 (NEXT)            add r7, r7, #1
  -                                mov r2, r6
  b   loop                         b   loop
```

**The three-instruction group is the guard temp coalescing into pos.**
`uncprop` rewrites a PHI argument that is the constant 0 into any SSA name
known to be 0 on that edge, and on the main path that name is the guard temp;
it does so for all seven `pos = 0` edges.  Out-of-SSA's coalesce costs then
*accumulate per edge* (`add_coalesce` adds, it does not max), so the guard
temp's seven beats `pos_6`'s two, the `orr` writes pos's own register, and pos
needs a second register plus a copy on the latch.

The obvious fix - give the guard value a type whose `TYPE_CANONICAL` differs
from pos's, so `gimple_can_coalesce_p` refuses - works: with
`((int)(pos | n)) | ((int)(pos & n))` and `pos` unsigned the PHI keeps its
constants, `end` and `m` pick the temp up exactly as the shipped build does,
and the latch copy disappears.  But it *also* re-creates a shared
`mov r2, #0` block for the main path, which the guard-true arms then merge
into, and the net is worse (edit distance 8 against 5).  The two effects are
coupled through the same block and that is the open question.

### Every way of making the guard's type differ, and what each costs

`gimple_can_coalesce_p` needs `TREE_TYPE` pointer equality or an equal
`TYPE_CANONICAL` plus `types_compatible_p`, so any of these blocks `uncprop`
for `pos` - and every one of them then pays the same layout price:

| guard / declaration | edit distance | size |
|---|---:|---:|
| `unsigned int pos`, `u32 n`, `(pos \| n) \| (pos & n)` (shipped-matching baseline) | **5** | +0 |
| `unsigned long pos`, `u32 n` | 7 | -4 |
| `u32 pos`, `unsigned int n` (the typedef distinction of section 15) | 8 | -8 |
| `unsigned int pos`, `u32 n`, `((int)(pos \| n)) \| ((int)(pos & n))`, `n` declared before `pos` | 8 | +0 |
| `int`/`s32`/`long` `pos`, `u32` `n` | 10 | -12 |
| `((int)(pos \| n)) \| ((int)(pos & n))`, `pos` declared before `n` | 10 | -8 |

Two spellings that look like they should work and do not, both for the same
reason - **a conversion that only feeds a comparison against zero is dropped**:

* `int g = pos | n; if (g)` - the cast disappears and `g` becomes the unsigned
  IOR itself, so `uncprop` is not blocked *and* VRP's
  `register_edge_assert_for` sees a bare `BIT_IOR_EXPR` again and proves `n`
  zero on the main path, which costs four more bytes;
* `int g = (pos | n) | (pos & n); if (g)` - same, and identical to the
  baseline.

Only the *inner* casts survive, because there the outer `|` is genuinely
`int`-typed and GIMPLE's type correctness requires them.

Swept, all compiled and scored against the shipped bytes: 2,592 structural
shapes; 16,807 type combinations over six locals; 5,184 more crossing the
types with three guards; 4,320 over all 720 declaration orders; 11,520 over
declaration order crossed with the arms, the `#` arm and the `\n` arm; and
about 8,000 over guard spellings.  Edit distance 21 -> 12 -> 5.

**The two-instruction group is `m`.**  The shipped build materialises
`m = (pick[j-1] == ' ' && buf[i] == ' ')` as 0/1 with a conditional-move pair
and then branches on the same flags; the `movne r7, #0` is dead, because every
path from it reaches `m = 1`.  Ours branches straight to the shared `m = 1`.

The mechanism is exactly the one in section 21's second half.  The C `&&`
gimplifies to `iftmp = PHI <1, 0>`; `phiopt` turns that into the comparison
itself, `m = iftmp` is a *copy* so copy-propagation merges the two names, and
then the branch and the value are the same SSA name: VRP asserts it non-zero
on the taken edge, its range is [0,1] so the value is 1, and the loop PHI's
argument on that edge becomes the constant 1 - which `phiopt` then merges with
the two other `1` arguments, so the whole assignment disappears.  For the
shipped shape the branch has to test a *different* SSA name from the one the
PHI carries.  Nothing that keeps the semantics does that: seven spellings of
the test and the assignment, `&` instead of `&&`, `!!`, `? 1 : 0`, five types
for `m` itself and five for an intermediate flag copied into it, and writing
the condition twice so FRE unifies it (which instead splits the fused
`cmp` / `cmpeq` into two branches and costs four bytes).  Every conversion is
either `useless_type_conversion_p` or folded away by VRP, because the value's
range is [0,1].

### What the type fix does and does not do

`uncprop_into_successor_phis` only rewrites a constant PHI argument into an
SSA name that `gimple_can_coalesce_p` accepts against the *PHI result*, and
that function requires `TREE_TYPE` pointer equality or an equal
`TYPE_CANONICAL` plus `types_compatible_p`.  So making the guard's type
differ from `pos`'s - `((int)(pos | n)) | ((int)(pos & n))` with `pos`
unsigned - is enough to stop it, and the dumps confirm it exactly:

```
pos_5 = PHI <pos_6(3), 0(6), 1(8), 0(9), 0(10), 0(13), 0(14), 0(17), 0(18), 0(15), pos_6(5), n_9(7)>
end_14 = PHI <..., _34(10), _34(13), ...>          <- end still picks the temp up
m_10  = PHI <..., _34(13), ...>                    <- and so does m
```

which is what the shipped build does, and the register cascade then comes out
*exactly* right: `orrs r9, r2, r6`, `moveq r2, r6`, `moveq r4, r6`,
`movne r6, #0` and the shared `mov r2, #0` all match the shipped word for word.

What breaks instead is **layout**, and the two passes that do it are named:

* out-of-SSA now has to emit a real `pos = 0` copy on each of the seven
  main-path edges.  `eliminate_phi` issues constant copies last and *from a
  stack*, so their order within an edge block is the reverse of the PHI order,
  which is the declaration order - that is why declaring `n` before `pos`
  swaps `mov r6, #0` and `mov r2, #0` inside the `n`-test arm.
* `pass_jump2`'s cross-jumping then merges those seven one-instruction blocks
  with each other *and* with the `n != 0` arm's own `pos = 0`, and
  `reorder_basic_blocks_simple` - which at `-Os` chains greedily in block
  order with no sort (section 12) - gives the loop tail to the earliest
  single-successor predecessor, which is now the arm block rather than the
  merged copy.  The tail moves from the end of the function to just after the
  guard, and 44 words differ instead of 44, but in different places: the edit
  distance goes 5 -> 8 with `n` declared first, 5 -> 10 with `pos` first.

Swept, all compiled and scored against the shipped bytes: 2,592 structural
shapes; 16,807 type combinations over six locals; 5,184 more crossing the
types with three guards; 4,320 over all 720 declaration orders; 11,520 over
declaration order crossed with the arms, the `#` arm and the `\n` arm; about
8,000 over guard spellings; and 20,160 more in this pass crossing the four
guard spellings with all 720 declaration orders and the arms.  Edit distance
21 -> 12 -> 5, and 5 is where it still is.

---

## 18. `ez_strsep`: TER puts the add on the wrong side of the store - closed

Three things were wrong; all three are now right and the function is
byte-identical.

**Block layout.**  Writing `if (*p == esc || *p == delim)` as two separate
`if`s, each with its own `memmove(q, p, strlen(q)); continue;`, reproduces the
shipped block order exactly.  Cross-jumping merges the two copies again and
keeps the *earlier* one, which is what puts the `*p == delim` test after the
memmove block (section 12).

**The delimiter path's last four words.**  The shipped is

```
	shipped                        ours (before)
 140	mov  r2, #0                    mov  r3, #0
 144	add  r3, r4, #1                strb r3, [r4], #1
 148	strb r2, [r4]                  str  r4, [r7]
 152	b    .+64  -> str r3, [r7]     b    .+68  -> mov r0, r6
```

The shipped delimiter path branches to the *same* `str r3, [r7]` the
end-of-string path uses.  `*stringp = NULL` became `str r3, [r7]` because
`cse1` knows r3 - the character just loaded and compared against zero - is zero
on that edge, and the delimiter path puts `q + 1` in the same r3 and
cross-jumps onto it.  That is only possible because the address is computed
*before* the NUL store, so `q` is still live at the store and cannot share a
register with `q + 1`.

The chain that stopped it, all three passes read out of GCC 6.5.0's own source
and confirmed in their own dumps:

1. **TER** (`tree-ssa-ter.c`, run inside `expand`) replaces an expression into
   its use when `ssa_is_replaceable_p` holds - which requires, among other
   things, `single_imm_use`.  `t = q + 1` is used once, by `*stringp = t`, so
   the add is emitted at the store no matter which order the source writes
   them in: `-fdump-rtl-expand` shows insn 76 `mem(p_110) = 0` then insn 77
   `t_129 = p_110 + 1`.
2. **`auto_inc_dec`** scans each block *backwards* (`merge_in_block`), keeping
   `reg_next_inc_use[reg]`, and `find_inc` looks only for an inc that comes
   *after* the memory reference (FORM_POST_ADD).  With the add after the store
   it finds it, `try_merge` prices the pair at 8 against 8 - `old_cost <
   new_cost` is false on a tie, so it fires - and
   `-fdump-rtl-auto_inc_dec-details` prints `found post add(77)`,
   `****success 76: [r129:SI++]=r127`.
3. The value is then in `q`'s own register, so the two `*stringp` stores are
   `str r4, [r7]` and `str r3, [r7]`, and cross-jumping cannot merge them.

### Which of the two passes actually decides it

`auto-inc-dec.c` has a `dbg_cnt (auto_inc_dec)`, so the fold can be blocked
*per site* without touching anything else.  There are exactly three folds in
this translation unit before `ez_strsep`'s delimiter path, so
`-fdbg-cnt=auto_inc_dec:2` blocks that one and keeps the loop's shipped
`ldrb r3, [r5], #1`.  **It is not enough.**  The result is

```
	mov r3, #0 ; add r4, r4, #1 ; strb r3, [r4, #-1] ; str r4, [r7]
```

- five instructions and four bytes too long, because with the add still
*after* the store `q` dies at the add, IRA gives the add's result q's own
register, and post-reload the pair is rewritten with a -1 displacement.

What *is* enough is putting the add before the store and keeping it there:
with the temporary written first and `-fno-tree-ter`, the function is
byte-identical - `n=0, d=+0`.  Then the post-reload scheduler emits
`mov`, `add`, `strb` in the shipped order (with `-fno-schedule-insns2` the pair
comes out `strb` then `add`), and cross-jumping merges the tail.

### The source-level lever

`ssa_is_replaceable_p` plus `ter_is_replaceable_p` and
`find_replaceable_in_bb`'s own checks leave exactly four source-level ways to
stop the sink:

| lever | why it was not used |
|---|---|
| a second immediate use of `q + 1` | no zero-cost second use exists: `r[-1] = 0` and `*(r - 1) = 0` are folded back to `*q` by forwprop, a second `*stringp = r` is removed by DSE, `p = r` and `q = r` are dead or copy-propagated, and every comparison against `q`, `s` or `NULL` either folds or costs a branch |
| the single use is a PHI | needs a merge point, which puts the shared `str` at the end of the function instead of at offset 64 (section 19) - unless the source carries a label in the middle of the loop body, which does reproduce the bytes but is a much larger deviation |
| the use is in another basic block | same: GCC 6 merges a block with its single-predecessor successor even across a user label (`gimple_can_merge_blocks_p` only refuses `FORCED_LABEL`), so this collapses to the previous row |
| **volatile operands on the use statement** | used: `find_replaceable_in_bb` calls `finished_with_expr` when `gimple_has_volatile_ops (stmt)` holds for the statement that *uses* the tracked expression |

So the reconstruction writes the delimiter arm as

```c
		if (c == delim) {
			r = q + 1;
			*q = '\0';
			*(char * volatile *)stringp = r;
			return s;
		}
```

and that is byte-identical.  The `volatile` is a compile-time device only: it
does not survive to the output, because cross-jumping merges this store with
the non-volatile `*stringp = NULL` of the end-of-string path into the single
`str r3, [r7]` at offset 64.  **This is a reconstruction, not recovered vendor
text.**  What is recovered from the binary is the *property*: the vendor's
build did not sink `q + 1` past the NUL store.  Their spelling is not
determined by the bytes - a `goto`-to-a-mid-loop-label form reproduces them
too.

Ruled out, all compiled and scored: the store order both ways; a named
temporary; `p = q + 1` before or after; `*q++ = '\0'`; `*stringp = ++q`;
`q += 1`; `&q[1]`; `q + sizeof(char)`; a cast through `unsigned long`;
`(*stringp)++`; carrying the walk pointer four different ways; `char` and `u8`
for the character; `for(;;)` and `while(1)`; advancing `p` before the delimiter
test (which removes the add entirely, because the value is then the loop's own
`p`, and costs four bytes); and the `r[-1]`, double-store, `q = r` and
`(unsigned long)` round-trip spellings above.

## 19. A shared tail is duplicated source

This is the rule that closed the last two big residuals, and it is the most
useful thing this pass found after section 12.

Section 12 established that at `-Os` block layout is source order: GCC 6's
`reorder_basic_blocks_simple` skips its edge sort entirely when optimising for
size, so blocks are chained in GIMPLE order.  The corollary took a while to
notice.  If a block in the shipped code is reached from two places, there are
two ways the source could have produced it - a `goto` to a common label, or two
copies that cross-jumping merged - and **they produce the same final layout by
different routes**.  What differs is the expression graph that reaches the
register allocator, because each duplicated copy is CSE'd, propagated and
scheduled in its own basic block before the merge happens.

Both remaining large residuals turned out to be that.

**`ez_scan_device_ioctl_handle`** was written here with `goto trig_scan`: the
two TRIG cases fill `probe_req_t` and jump to a shared tail.  The vendor wrote
the tail twice.  With the whole body - the `if (len)` copy, the zero-length
check, the five printks, the `rtw_ezviz_ie_set` call - duplicated into both
arms, the function is byte-identical, pool included.  The mechanism:
`probe_req_t.id` is an unaligned `u16` in a packed struct, so GCC builds
`&probe_req_t` explicitly to address the two byte stores; the memcpy
destination builds it again.  With the `goto` the two live in different basic
blocks, nothing combines them, and `cse_local` folds the second into the single
constant `.LANCHOR0+622` - which has to go in the literal pool, because 622 is
not an encodable ARM immediate.  Duplicated, the two are in the same block,
`&probe_req_t` survives as `add r5, r4, #612`, and `&probe_req_t.value` is
`add r0, r5, #10`.  That one pool word was displacing eleven relocations:
`.rel.text` went 280 -> 32 bytes and the whole file 348 -> 96.

**`ez_strsep`** is the same shape one level down: `*p == esc || *p == delim`
written as two `if`s, each with its own `memmove(q, p, strlen(q)); continue;`.
Cross-jumping merges them and keeps the earlier copy, which is what puts the
`*p == delim` test after the memmove block.  Six instruction-level differences
become three.

**`process_config_vars`** got a third variant of it: `pos = 0` written at the
end of each path that falls out of the selector rather than once after it.
That, plus writing the selector as an if-chain instead of a `switch`, plus
`pos` and `n` having different tree types (section 15), took the edit distance
from 21 to 12 and the whole file 96 -> 56.

The practical rule for reading shipped code: **a `goto` in a reconstruction is
a hypothesis, not an observation.**  Try the duplicated form as well - it costs
one variant.

---

## 20. `.text` order is the call graph, not the source - and `oemdiff` hid it

This was 873 of the 1,002 differing bytes of `.text` plus every byte outside
it, and the per-function harness reported all four functions involved as
byte-identical.

`oemdiff.py` compares an *object* to the linked module.  It cannot do that
positionally, so it masks every word that carries a relocation and every
`B`/`BL` displacement and compares those symbolically instead - target symbol,
addend, resolved callee.  That is what makes it usable, and it is also how four
functions that were in the wrong *place* passed as clean: their content is
identical, so every symbolic comparison matched, while in the linked module
they sat at different addresses.

A plain `cmp` of the two modules, bucketed by symbol, is the check that finds
it:

```
   378  ez_probe_requst_eid208_handler
   247  ez_probe_response_eid208_handler
   143  check_probe_sync_eid208
   105  ez_probe_req_handler
```

Laying the two symbol tables side by side shows a rotation:

```
   shipped   ... check_sn_valid  check_probe_sync_EID  ez_probe_req_handler
                 check_probe_sync_eid208  response  requst  ez_scan_device_ioctl_handle
   ours      ... check_sn_valid  check_probe_sync_EID
                 check_probe_sync_eid208  response  requst  ez_probe_req_handler  ez_scan...
```

### Why the order is what it is

GCC emits functions in the reverse of `ipa_reverse_postorder`, a depth-first
walk of the call graph over *callers*.  The practical consequence is visible in
both modules: `check_probe_sync_EID` is defined at line 48 of `ez_sc.c` but
emitted near the end, immediately before `ez_probe_req_handler` - the function
that calls it - and it drags `check_sn_valid`, which *it* calls, along in front
of it.  So the position of one root function in the source decides where a
whole chain lands in `.text`.

`ez_probe_req_handler` had been placed immediately before
`ez_scan_device_ioctl_handle` by the DECL_UID oracle (section 11).  That
placement satisfies the uniquifiers but puts the chain after the three EID208
handlers.  Compiling the same file with the function spliced in at each of the
26 top-level positions in turn and reading `nm -n` off each object shows that
**any** position before `check_probe_sync_eid208` reproduces the shipped order,
and every position after it does not:

```
   00..19  ... check_sn_valid check_probe_sync_EID ez_probe_req_handler
               check_probe_sync_eid208 response requst ez_scan_device_ioctl_handle   <- shipped
   20..21  ... check_probe_sync_eid208 ez_probe_req_handler response requst ...
   24..25  ... response requst ez_probe_req_handler ez_scan_device_ioctl_handle      <- was
```

### Which of those twenty the oracle picks

Moving the function moves its eight DECL_UIDs (`2 + max(nparams,1)` for the
definition, plus four locals) from the
`ez_probe_requst_eid208_handler -> ez_scan_device_ioctl_handle` interval into
whichever interval it lands in, and each interval's total is pinned exactly.
Only one interval has a placeholder big enough to give eight back:
`check_probe_sync_EID -> rtw_ezviz_ie_set`, whose `ez_sc_uid_gap_1` was ten.
So the function goes immediately after `check_probe_sync_EID` - the function it
calls - `ez_sc_uid_gap_1` shrinks from ten declarations to two, and
`ez_sc_uid_gap_7` grows from 27 to 35.  All eight intervals are exact and all
879 uniquifiers still match.

Moving `check_sn_valid` instead was tried and rejected: it is reachable only
through `check_probe_sync_EID`, so `.text` does not move, but it changes which
`.LANCHOR` offsets `check_sn_valid` uses for `DeviceInfo` and `null_sn` and the
function stops matching.

### The result

| | before | after |
|---|---:|---:|
| `.text` | 1,002 | 102 |
| `.rodata.str1.1` | 208 | 0 |
| `.rel.text` | 161 | 0 |
| `.ARM.exidx` | 13 | 0 |
| `.symtab` | 17 | 0 |
| whole file | 1,421 | 141, then 121 |
| byte-identical sections | 35/41 | 39/41 |

`.rodata.str1.1` moved because string constants are emitted in the order the
functions that use them are emitted; `.rel.text`, `.ARM.exidx` and `.symtab`
because they are indexed by address.

**The rule:** a per-function harness that compares symbolically cannot see a
placement error.  Check the linked module positionally as well, bucketed by
symbol - `build/oem/align.py` and a bare `cmp` are enough.

---

## 21. `ez_new_sc_ioctl`: the IRA numbers, and the decision they hang on

Five words of fourteen, and the whole difference is which of two allocnos gets
r1.  `-fira-verbose=9` (10 sends the same text to stderr instead of the dump
file) prints the entire state of this function:

```
  a0(r124,l0) costs: GENERAL_REGS:0 MEM:20000       <- is_null, 2 references
  a1(r116,l0) costs: GENERAL_REGS:0 MEM:30000       <- rq,      3 references
;; a0(r124,l0) conflicts: a1(r116,l0)
;;     total conflict hard regs: 0 2
;; a1(r116,l0) conflicts: a0(r124,l0)
;;     total conflict hard regs: 0
  pref0:a0(r124)<-hr1@2000
  pref1:a1(r116)<-hr1@2000
  pref2:a1(r116)<-hr2@125
      Pushing a0(r124,l0)(cost 0)
      Pushing a1(r116,l0)(cost 0)
      Popping a1(r116,l0)  -- assign reg 2
      Popping a0(r124,l0)  -- assign reg 1
```

r116 is `rq` (insn 12 is `r116 = r1`, the incoming parameter) and r124 is
`is_null` (insn 30 is `r1 = r124`, the second outgoing argument).  Both want
r1 at 2000; they conflict, so in `assign_hard_reg` the neighbour's preference
is subtracted from the full cost and the two cancel exactly.  What is left is
`rq`'s weight-125 preference for r2, which comes from `ira-conflicts.c`'s
`process_reg_shuffles`: `rq` *dies* in insn 29, `r2 = r116 + 16`, whose
destination is the hard argument register, so IRA records a copy between them.
r2 therefore wins by 125 and `rq` moves there, costing `mov r2, r1` at the top.

### The decision is the *push order*, and the push order is the reference count

The 125 only decides anything because **`rq` is popped first**.  `Popping` is
`push_allocnos_to_stack` unwinding a stack that `push_only_colorable` filled
from the head of a bucket sorted by `bucket_allocno_compare_func`, whose first
key is `ALLOCNO_COLOR_DATA (t)->thread_freq` - and `init_allocno_threads` sets
that to `ALLOCNO_FREQ`, which `create_insn_allocnos` accumulates as
`REG_FREQ_FROM_BB` per *reference*.  At `-Os` `REG_FREQ_FROM_BB` is the
constant `REG_FREQ_MAX` = 1000 for every block, so **`ALLOCNO_FREQ` is exactly
1000 x the number of times the pseudo appears in the RTL**.  The allocno with
the *lower* frequency sorts to the head, is pushed first, and is therefore
coloured **last**.

`rq` appears three times (the parameter copy, the null test, the address add);
`is_null` twice (the cstore that defines it, the argument move).  3000 beats
2000, so `is_null` is pushed first and `rq` is coloured first - and takes r2.

Reverse it and the shipped assignment falls out, with no other change:

```
  a0(r124,l0) costs: ... MEM:40000        <- is_null, 4 references
  a1(r116,l0) costs: ... MEM:30000
      Pushing a1(r116,l0)(cost 0)
      Pushing a0(r124,l0)(cost 0)
      Popping a0(r124,l0)  -- assign reg 3
      Popping a1(r116,l0)  -- assign reg 1
```

`is_null` is coloured first; its hr1@2000 is cancelled by `rq`'s, which is
still unassigned, so every profitable register costs the same and it takes the
first in ARM's `REG_ALLOC_ORDER` - which is `3, 2, 1, 0, 12, 14, ...`, and r0
and r2 conflict, so r3.  Then `rq` is coloured with no unassigned conflicting
neighbour left, its hr1@2000 stands unopposed, and it keeps r1.  That is
`ez_new_sc_ioctl` byte-identical: `n=0, d=+0`.  Equality is *not* enough -
with three references each the tie-break leaves the order as it was and
nothing changes.

### What is still open

The construction above was demonstrated with two `__asm__ __volatile__("" ::
"r"(is_null))` statements, which emit nothing but count as references.  **No
ordinary-C spelling has been found that adds them.**  What was tried and
measured (each printed the *identical* IRA state - same two allocnos, same two
reference counts, same preferences, same push order):

* seven types for the flag, and a second flag variable of a different type
  (`unsigned int`, `u32`, `s32`, `u8`, `long`) copied from it - every one of
  those conversions is `useless_type_conversion_p` or is folded away by VRP
  because the value's range is [0,1], so no statement survives to expand;
* the flag written as a diamond (`is_null = 0; if (...) is_null = 1;`) and as
  its inverse - `phiopt`'s `conditional_replacement` collapses `PHI <0, 1>`
  back to the comparison;
* `return -is_null;` in the error arm - VRP asserts `is_null != 0` on that
  edge, its range is [0,1], so the value is 1 and it folds back to `-1`;
* a repeated `if (is_null) return -1;` after the guard - VRP deletes it;
* the pointer round trips (`(unsigned long)rq`, `(struct iwreq *)(unsigned
  long)rq`, the address computed as `(struct iw_point *)((unsigned long)rq +
  16)`), five spellings of the third argument, four of the null test, guard
  clause / `if`-`else` / a `ret` variable / `goto`, and the address computed
  before and after the branch.

Two further routes are closed by mechanism rather than by sweeping:

* **Removing a reference from `rq` instead.**  Its three are the parameter
  copy, the test and the add.  `combine` eliminates a parameter copy only when
  the pseudo dies in the insn it is substituted into - which is why `dev`'s
  copy disappears (its only surviving use is the compare, in the same block)
  and `rq`'s does not (the address add is in another block).  Moving the add
  into the first block makes both uses local and does remove the allocno
  entirely, but then the add is emitted before the branch, which is four bytes
  and one instruction away from the shipped layout.
* **Block frequencies.**  `REG_FREQ_FROM_BB` is the constant `REG_FREQ_MAX`
  whenever `optimize_function_for_size_p`, which is unconditionally true at
  `-Os`.  A reference in the cold error arm and a reference on the hot path
  contribute identically, so `unlikely()` / `__builtin_expect` cannot move this
  tie at all - not "not enough", but not at all.

---

## 22. Harness audit: every masked field, and the check that covers it

A comparison harness that masks a field is a harness that cannot report it.
Section 20 cost this reconstruction 1,280 bytes for exactly that reason, so
here is the complete list of what each tool hides and what catches it instead.

| tool | what it masks | covered by |
|---|---|---|
| `fulldiff.py` structural count | charges a wrong-sized function only its size *delta* and never looks inside it; a function that moved but kept its name and size is charged **nothing** | the **RAW** count in the same run - a plain positional compare of the whole file, headers included - and the per-section `byte-identical sections: N/41` line |
| `fulldiff.py` `.symtab` / `.strtab` name comparison | strips GCC's `.NNNN` `DECL_UID` uniquifier before comparing, so renumbered locals score 0 | the RAW count (which compares `.strtab` byte for byte) and `build/oem/uidgap.py`, which pairs every `.NNNN` symbol by section and address and prints the per-interval declaration deficit |
| `fulldiff.py` `reloc` and `branch` counters | relocation addends and `B`/`BL` displacements are reported but excluded from the structural `total` | printed on their own summary line every run, and included in RAW |
| `oemdiff.py` | compares an *object* to the *linked* module, so every word under a relocation is compared symbolically (target symbol, addend, string contents) and every `B`/`BL` by its resolved callee; a function at the wrong address scores clean | the RAW count, and `fulldiff.py`'s per-symbol `st_value` check - every one of the 3,909 symbols is required to be at the shipped address |
| `align.py` `s` score | blanks the register fields, so a function that differs only in allocation scores 0 | the `n` count (differing 4-byte words) printed beside it, and RAW |
| `lab.py` | reports `n`, `d` and `s` from the two above | same |

Two structural properties make the list closed rather than merely long:

* **Nothing is compared only per symbol.**  `fulldiff.py` walks all 41
  sections and compares each in full, and prints `bytes outside any sized
  symbol` for every one of them, unconditionally and untruncated - the byte
  counts are equal on both sides in every section, so no byte of the file is
  unattributed.
* **RAW is a compare of the whole file**, not a sum of per-object verdicts, so
  anything the symbolic tools mask still lands in it.

### The check was tested by breaking it again

Reverting only the section-20 fix - moving `ez_probe_req_handler` back after
`check_probe_sync_eid208` - and rebuilding gives:

```
  oemdiff.py (per function, symbolic)   44/46 byte-identical, 8336/8736 bytes   <- unchanged
  fulldiff.py STRUCTURAL                192 bytes                               <- unchanged
  fulldiff.py RAW                       116 -> 519 bytes                        <- fires
  byte-identical sections                39 -> 34                               <- fires
```

Both symbolic verdicts are blind to it and both positional ones catch it.  That
is the reason **RAW is the headline number** everywhere in this repository, and
the reason the section count is printed next to it.
