#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>
#include <linux/usb.h>
#include <linux/timer.h>
#include <linux/spinlock.h>
#include <linux/mutex.h>
#include <linux/workqueue.h>
#include <net/cfg80211.h>
#include <linux/wireless.h>
#include <net/iw_handler.h>

/* Each global's symbol size == sizeof() of the struct, readable with readelf. */
#define PROBE(nm, ty) char probe_##nm[sizeof(ty)];
PROBE(module,        struct module)
PROBE(wiphy,         struct wiphy)
PROBE(net_device,    struct net_device)
PROBE(sk_buff,       struct sk_buff)
PROBE(device,        struct device)
PROBE(usb_device,    struct usb_device)
PROBE(usb_interface, struct usb_interface)
PROBE(timer_list,    struct timer_list)
PROBE(spinlock_t,    spinlock_t)
PROBE(mutex,         struct mutex)
PROBE(semaphore,     struct semaphore)
PROBE(work_struct,   struct work_struct)
PROBE(delayed_work,  struct delayed_work)
PROBE(completion,    struct completion)
PROBE(wireless_dev,  struct wireless_dev)
PROBE(iw_handler_def,struct iw_handler_def)
PROBE(iw_statistics, struct iw_statistics)
PROBE(dev_pm_info,   struct dev_pm_info)
PROBE(kobject,       struct kobject)
PROBE(napi_struct,   struct napi_struct)
MODULE_LICENSE("GPL");
