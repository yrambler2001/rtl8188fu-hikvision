# Kernel-config oracle

`probe.c` declares one global per kernel struct, sized by `sizeof()`. The symbol
sizes in the resulting `probe.ko` are therefore the struct sizes for whatever
kernel config is currently prepared:

```sh
docker run --rm --platform linux/arm64 -v "$PWD/build/probe":/probe \
    rtl8188fu-build sh /probe/run.sh
```

It builds in seconds, so kernel config space can be searched cheaply
(`search.sh` / `search2.sh` are examples) instead of rebuilding the whole driver.

## Targets recovered from the shipped 8188fu.ko

| measurement | how it is visible in the binary | target | status |
|---|---|---:|---|
| `sizeof(struct module)` | size of the `__this_module` symbol | **384** | **matched** |
| `ALIGN(sizeof(struct net_device), 32)` | `netdev_priv()` offset, appearing as the `ldr/str` immediate in `rtw_alloc_etherdev_with_old_priv`, `cfg80211_rtw_*`, … | **992** | 1120 (128 to go) |
| `sizeof(struct iw_handler_def)` | size of `rtw_handlers_def` | **24** | **matched** (needs `CONFIG_WEXT_PRIV`) |

## Config recovered so far

`struct module` reaches exactly 384 by disabling: `KALLSYMS`, `JUMP_LABEL`,
`UNUSED_SYMBOLS`, `CONSTRUCTORS`, `FTRACE`, `PERF_EVENTS`, `TRACING`,
`DEBUG_SET_MODULE_RONX`, `MODULES_TREE_LOOKUP`.

`CONFIG_PM_SLEEP=n` shrinks the embedded `struct device` by 32 bytes, moving the
`net_device` delta from +160 to +128 — confirming the mechanism, though the
struct is not yet an exact match.

Note that partial struct matches do not improve the byte-identical function
count: a struct is either laid out identically or it is not.
