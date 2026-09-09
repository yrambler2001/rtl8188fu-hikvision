# Target platform, recovered from the firmware

The camera's SoC is **Fullhan (Shanghai Fullhan Microelectronics, 富瀚微) FH865X**, not
HiSilicon. Evidence, all from the extracted rootfs:

| artifact | what it proves |
|---|---|
| `modules/rtthread_arc_FH865X.bin` | SoC family name, verbatim |
| `libys_vqe_fh865x_20231026.so`, `c2det_230824_865x.nbg` | same |
| `bgm.ko enc.ko isp.ko jpeg.ko media_process.ko nna.ko vmm.ko vpu.ko xbus_rpc.ko` | all `author=FULLHAN` |

Every one of those vendor modules carries the same two strings as `8188fu.ko`:

```
vermagic = 4.9.129 mod_unload ARMv7 p2v8
.comment = GCC: (arm_multilib_uclibc_20200924) 6.5.0
```

So the whole firmware is one kernel + one toolchain, and any of those modules is a
valid oracle for the vendor kernel's struct layout.

The kernel image itself (`uimage_03c0000_Linux.payload.bin`, 2329600 bytes, uImage
header says "Not compressed", load 0xA0008000) is **encrypted** - entropy 8.000,
no `Linux version` banner, no `IKCFG_ST` magic, no gzip streams. So `/proc/config.gz`
extraction is not available from this image.

## Config facts proven by the undefined-symbol list of the shipped `8188fu.ko`

`depends=` in `.modinfo` is **empty**, and the module references `cfg80211_*`,
`register_inet6addr_notifier` and `usb_*`. A module only gets a `depends=` entry for
symbols exported by another *module*, so:

* `CONFIG_CFG80211=y` (built-in, not `=m`)
* `CONFIG_IPV6=y`   (built-in)
* `CONFIG_USB=y`    (built-in)

Further, from which out-of-line helpers are referenced:

| observation | conclusion |
|---|---|
| no `_raw_spin_lock*`, no `_raw_read_lock*` | `CONFIG_SMP=n`, `CONFIG_DEBUG_SPINLOCK=n` -> `spinlock_t` is 0 bytes |
| `kmem_cache_alloc` present, `kmem_cache_alloc_trace` absent | `CONFIG_TRACING=n` |
| no `__gnu_mcount_nc` | no ftrace / function tracer |
| no `__stack_chk_fail` | no stack protector |
| no `preempt_count_add` / `preempt_count_sub` | `CONFIG_PREEMPT_COUNT=n` -> `CONFIG_PREEMPT=n` |
| no `_cond_resched` | suggests `CONFIG_PREEMPT_NONE=y` rather than `PREEMPT_VOLUNTARY` |
| no `pm_runtime_*`, `device_set_wakeup_*`, `wakeup_source_*` | consistent with `CONFIG_PM=n` |
| `PDE_DATA`, `proc_create_data`, `seq_*`, `single_open_size` | `CONFIG_PROC_FS=y` |
| `__vfs_read` / `__vfs_write` | driver reads firmware files directly |
| `arm_copy_from_user`, `__do_div64`, `__memzero`, `arm_delay_ops` | stock ARM |
