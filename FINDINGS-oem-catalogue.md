# The OEM code: `ez_sc.c` and `ez_wifi_config.c`

Everything the shipped `8188fu.ko` contains that no public Realtek release does.
This note is the catalogue WP-D was asked for: what the two missing translation
units are, what is in them, how each fact was read out of the binary, and where
the reconstruction stands.

**Result so far:** the whole-file gap went **28,368 -> 455 bytes** (1.479% ->
**0.024%** of 1,918,056). Every section except `.text`, `.rel.text`, `.symtab`,
`.strtab` and `.note.gnu.build-id` is byte-identical - `.rodata.str1.1`,
`.rodata`, `.data`, `.bss`, `.comment`, `.modinfo`, `.ARM.exidx`, the ARM
attributes and eleven of the twelve relocation sections - and `.symtab` has the
right size, the right entry count and no missing or extra symbol. **42 of the 46
OEM functions are byte-identical**, and so are all four public functions the OEM
patch distorts, plus `rtw_efuse_analyze` (section 14). Sections 10 to 14 are the
current state; sections 1 to 9 are the original WP-D catalogue.

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
python3 build/oem/oemdiff.py --shipped /path/8188fu.ko --catalogue
```

`oemdiff.py` compares an object file to the linked module, which cannot be done
positionally: bytes under a relocation are masked and compared symbolically
instead (target symbol, addend, and for `.rodata.str1.1` the actual string),
B/BL words by their resolved callee, intra-function branches by their offset
from the function start, and GCC's `.NNNN` uniquifier is stripped from symbol
names. `annot.py` resolves literal-pool addends so the shipped code is readable.

---

## 10. Where this stands, and what is left

`python3 build/fulldiff.py <shipped> ./8188fu.ko --brief`:

| | bytes | share of file |
|---|---:|---|
| before WP-D | 28,368 | 1.479% |
| start of this pass | 972 | 0.051% |
| **now** | **455** | **0.024%** |

| section | structural | what it is |
|---|---:|---|
| `.rel.text` | 312 | relocations inside the four functions below |
| `.text` | 116 | those four functions |
| `.note.gnu.build-id` | 19 | an SHA-1 of the module; converges last, by construction |
| `.symtab` | 8 | two `st_size` fields |

Everything else is byte-identical, including every string, every data object,
every unwind entry and eleven of the twelve relocation sections.  `.strtab` is
15 bytes short and 14 of its 5,723 strings differ - all of them
`__func__.NNNN` / `__FUNCTION__.NNNN` uniquifiers belonging to the two OEM
files; see section 11.

### Closed during this pass

| function | was | how |
|---|---|---|
| `ez_device_info_ioctl_handle` | -4 | `wrq->u.data.length` is a `__u16`, and the local it is read into is `u16`, not `u32`. Only then is `len - 9` a signed subtraction, which is what makes GCC keep it in the return register across the second `copy_from_user`. |
| `ez_mac2u8` | +4 | returns `void`. The shipped epilogue has no `mov r0,#0` and nothing calls the function. |
| `ez_wifi_func_poll_ioctl_handle` | 24 content | block order, see section 12. |
| `ez_probe_requst_eid208_handler` | 60 content | the `struct ez_tlv_t` is filled in field order *after* `probe_resp_t` is updated. All 120 orderings of the five statements were tried; exactly one is byte-identical. |
| `ez_set_new_sc` | -12 | `sc_cmd` is `int sc_cmd[2]`, not `u32`; and `NEW_SC_POLL_RESULT` tests the zero case first. See section 13. |
| `rtw_efuse_analyze` | +4 | not OEM code at all - the vendor's one added line in `core/efuse/rtw_efuse.c` is a **brace**, see section 14. |
| `process_config_vars` | +24 -> +8 | the `memcmp` result goes in a local so the call is unconditional, and the declaration order of the five `int` locals is `pos, n, m, j, end`. |
| `ez_scan_device_ioctl_handle` | +12 -> +4 | `sc.len` is copied into a `u8 len;` before the `probe_req_t` fill; the `POLL_REASON` reason word is a `u8 reason[4]`, not a `u32`; the else arm sets `sc.len = 1; sc.value[0] = 0xff`. |

**42 of 46 OEM functions are byte-identical** (`build/oem/run.sh`), and so are
all four public functions the OEM patch distorts.

### The four that remain

| function | delta | what is known |
|---|---:|---|
| `process_config_vars` | +8 | Two instructions. The shipped build spills `pick` to the stack (`stm sp, {r2, r3}` at entry, two reloads) and so has a spare callee-saved register for the `pos \| n` value, which lets `pos` live in one register throughout; ours keeps `pick` in `sl`, which splits `pos` across two registers and costs a copy on the loop back-edge and on the `\r` path. IRA's dump names the cause exactly: the shipped build has 12 allocnos restricted to r3-r11 and spills the three cheapest (`len`, `var`, `pick`); ours has 11 and spills two, because our `n` is redefined on every exit from the switch's default case and so does not cross the calls. That redefinition is VRP folding `n` to 0 inside the switch (from the `(pos\|n) == 0` assertion) and `uncprop` then writing the OR value back in its place. All 120 declaration orders x 7 types for `n` were swept; none produces the spill. |
| `ez_scan_device_ioctl_handle` | +4 | One instruction plus one literal-pool word. The shipped build materialises the OEM `.bss` anchor once into a callee-saved register and derives `&probe_req_t` as `add r5, r4, #612` and `&probe_req_t.value` as `add r0, r5, #10`; ours loads the anchor twice (caller-saved for the byte stores, callee-saved for what must survive the `memcpy`) and loads `&probe_req_t.value` from the pool. This is GCC's section-anchor costing; local pointer variables, member-access rewrites and every declaration order leave it unchanged. |
| `ez_strsep` | 80 content | Right size. Reconstructed instruction by instruction. Two differences. (a) Ours if-converts `*p == esc \|\| *p == delim` into `cmp`/`cmpne` where the shipped build branches to a second test placed after the `memmove` block; writing it as two `if`s with a duplicated `memmove` reproduces the shipped block order exactly (section 12). (b) The loop is `q = p; c = *p++;`, so in GIMPLE `q` is literally the loop PHI's value and out-of-SSA has to pick which copy to remove: coalescing the PHI with the post-increment pseudo (shipped - `mov r4, r5; ldrb r3,[r5],#1`, nothing on the back edge) or with `q` (ours - `mov r4, r5; ldrb r3,[r4],#1`, plus `mov r5, r4` on the back edge). They cannot both be coalesced, `q` interferes with `p + 1`, and both copies have the same loop frequency. That one extra copy is why (a) alone leaves the function 4 bytes long, so the short-circuit form is kept: a wrong `st_size` would also break `.symtab`. Fourteen loop shapes - pointer-carried, index-carried, `q = p++`, `p - 1`, `do`/`while`, inner-scope declarations - leave the choice unchanged. |
| `ez_new_sc_ioctl` | 20 content | Right size, same eight instructions, different order: the shipped build computes the null-check boolean into `r3` and keeps `rq` in `r1` until `add r2, r1, #16`; ours copies `rq` to `r2` first and computes the boolean into `r1`. IRA's dump gives the mechanism exactly. There are two allocnos and three preferences: `pref0: is_null <- hr1 @2000` (from the outgoing argument copy), `pref1: rq <- hr1 @2000` (from the incoming parameter copy) and `pref2: rq <- hr2 @125`. The two `@2000`s cancel, because the allocnos conflict and `update_conflict_hard_regno_costs` charges each the other's preference; the `@125` does not, so `rq` takes `r2` and `is_null` falls to `r1`. That third preference comes from the `add r2, rq, #16` that sets up the *third* argument - IRA treats an insn whose output is a hard register as copy-like. Without it, `rq` would take `r1` and `is_null` `r3`, which is the shipped code exactly. Twenty-two source shapes and nine types for `is_null` were tried; none removes the preference, because every spelling of `&wrq->u.data` folds back into that one `add`. |

### Next steps, in the order worth doing them

1. `process_config_vars` and `ez_scan_device_ioctl_handle` are one instruction
   each and both are allocator decisions with a known cause; a GCC built with
   `-fdump-ipa-all`/instrumented IRA cost dumps would settle them.
2. `ez_strsep` needs the split escape test without the loop back-edge copy -
   i.e. GCC coalescing the post-increment pseudo with the loop phi instead of
   with `q`.
3. The 16 OEM `__func__` uniquifiers in section 11.
4. `.note.gnu.build-id` will match by itself when the rest does.

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

**Result: 863 of 879 uniquified symbols match exactly**, `.strtab` is back to
within 15 bytes of the shipped size, and `.symtab` is down from 127 `st_size`
mismatches to 2.

### The 16 that remain, and what they say about the OEM sources

The uniquifiers also fix the vendor's **source order**, which `.text` order
cannot (`.text` is reverse postorder of the call graph).  Two functions were in
the wrong place and have been moved: `check_probe_sync_EID` has the lowest
`__func__` UID in ez_sc.c (70989) yet sat thirteenth in the file, and
`ez_wifi_preinit` belongs between `ez_set_country` and
`ez_read_rssi_per_ant_ioctl`.  Moving `check_probe_sync_EID` to just before
`set_scan_flag` puts its uniquifier at exactly 70989.

What is left is a per-gap declaration deficit - the vendor's functions declare
more than ours do.  Reading the gaps between consecutive `__func__` UIDs:

```
ez_sc.c            gap                        vendor  ours  short by
  check_probe_sync_EID -> rtw_ezviz_ie_set        66    56     10
  -> ez_new_sc_ioctl_handle                       12    11      1
  -> ez_device_info_ioctl_handle                  17    13      4
  -> check_probe_sync_eid208                      16    21     -5
  -> ez_probe_response_eid208_handler             11    10      1
  -> ez_probe_requst_eid208_handler                9     8      1
  -> ez_scan_device_ioctl_handle                  46    10     36
                                                            = 48

ez_wifi_config.c   before ez_set_country                            9
  ez_set_country -> ez_wifi_preinit               16    17     -1
  ez_wifi_preinit -> ez_read_rssi_per_ant_ioctl   18    19     -1
  -> ez_get_mac_addr                              50    44      6
  -> ez_wifi_func_poll_ioctl_handle               34    34      0
  -> ez_read_efuse                                 9     8      1
  -> ez_wifi_module_rf_calibration_check_ioctl    43    40      3
                                                            = 17
```

The kernel builds with `-Wno-unused-variable` and `-Wno-unused-but-set-variable`,
so unused locals - and `static` helpers that `-Os` inlines and deletes - cost
DECL_UIDs and leave no other trace.  65 such declarations across the two files
is entirely ordinary vendor code, but *which* they were is not recoverable from
the binary, and inventing 65 named locals inside reconstructed OEM function
bodies would be fabrication rather than reconstruction.  They are left as a
measured residual.  The gap arithmetic above is the complete statement of what
is missing; anyone who recovers the real sources can check it in one step.

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
