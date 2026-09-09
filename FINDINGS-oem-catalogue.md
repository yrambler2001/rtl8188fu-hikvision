# The OEM code: `ez_sc.c` and `ez_wifi_config.c`

Everything the shipped `8188fu.ko` contains that no public Realtek release does.
This note is the catalogue WP-D was asked for: what the two missing translation
units are, what is in them, how each fact was read out of the binary, and where
the reconstruction stands.

**Result so far:** the whole-file gap went **28,368 -> 1,296 bytes** (1.479% ->
**0.068%** of 1,918,056). 34 of 41 sections are byte-identical, including
`.rodata.str1.1`, `.rodata`, `.data`, `.bss`, `.comment`, `.strtab` and eleven of
the twelve relocation sections. 37 of the 46 OEM functions are byte-identical,
and so are all four public functions the OEM patch distorts.

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
current reconstruction (37/46). Callees and referenced objects come from
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
| **now** | **1,296** | **0.068%** |

| section | structural | what it is |
|---|---:|---|
| `.rel.text` | 1,048 | relocations inside the nine functions below |
| `.text` | 188 | those nine functions |
| `.symtab` | 32 | their `st_size` fields |
| `.note.gnu.build-id` | 20 | an SHA-1 of the module; converges last, by construction |
| `.ARM.exidx` | 8 | unwind words for two of them |

### The nine functions still differing

None of them differs in *content* in any way that has been traced to a semantic
error; every one is a register-allocation or basic-block-ordering difference.

| function | delta | what is known |
|---|---:|---|
| `ez_scan_device_ioctl_handle` | +12 | Cases must be in numeric order (0,1,2,3,4) with `TRIG_SCAN_DEVICE` jumping into `TRIG_SCAN_REASON`'s tail - that much is done. What remains: the shipped code keeps the `.bss` anchor in a callee-saved register and forms `&probe_req_t` once as `anchor+612`; ours reloads addresses from the literal pool. Suspect one extra live value. |
| `process_config_vars` | +24 | the scanner's flag variables; the reconstruction is behaviourally right but uses one more temporary than the vendor's |
| `ez_set_new_sc` | -12 | shipped keeps `ret` in a callee-saved register shared with the switch selector and has one shared epilogue; ours returns `-EFAULT` early |
| `ez_probe_requst_eid208_handler` | -12 | the 0x6992 branch's 4-byte TLV append |
| `ez_strsep` | -8 | the `*stringp == '\0'` early return returns `(char *)(unsigned char)*s`, i.e. a `ldrb`, not a plain NULL |
| `ez_device_info_ioctl_handle` | -4 | shipped holds `len - 9` in the return register across the `copy_from_user` |
| `ez_mac2u8` | +4 | dead code; the `ez_strsep` loop shape |
| `ez_wifi_func_poll_ioctl_handle` | 24 content | which of the two error blocks falls through to the shared `ret = -1` |
| `ez_new_sc_ioctl` | 20 content | the second argument to `ez_set_new_sc` really is the null-check boolean; ours computes it into the argument register, the shipped into a scratch |

Plus one non-OEM residual: **`rtw_efuse_analyze` (+4)**, unchanged from
`FINDINGS-byte-gap.md` section 4.2 - 591 of 634 instructions identical, one
six-instruction window where the shipped build keeps two string addresses live
in `r7`/`r8` across a `printk` and ours rematerialises one from the pool. The
`-fmerge-constants` explanation is disproved there; the standing hypothesis is
that the vendor's one added line in `rtw_efuse.c` sits inside or above this
function and shifts register pressure. Nothing in the OEM code found so far
explains it.

### Next steps, in the order worth doing them

1. **`ez_scan_device_ioctl_handle`** (+12) and **`process_config_vars`** (+24)
   are the two biggest and both look like one-extra-live-value problems. Compare
   `-fdump-rtl-ira` between the two builds rather than guessing at C shapes.
2. **`ez_strsep`** (-8): work out the exact early-return expression; then
   `ez_mac2u8` (+4) will likely follow, since it is only the loop around it.
3. The four <=12-byte ones are register allocation; the `--fn NAME -v` dump names
   the exact instruction in each case.
4. `rtw_efuse_analyze` (+4) - try inserting the vendor's one line at different
   points in `core/efuse/rtw_efuse.c` and watch the function; the `__LINE__`
   constraint only says it is above line 2876.
5. `.note.gnu.build-id` will match by itself when the rest does.
