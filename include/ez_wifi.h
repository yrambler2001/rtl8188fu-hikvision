/******************************************************************************
 *
 * OEM (EZVIZ / Hikvision) additions to the Realtek rtl8188FU driver.
 *
 * Reconstructed from the shipped 8188fu.ko -- the two translation units
 * ez_sc.c and ez_wifi_config.c are not part of any public Realtek release.
 * See FINDINGS-oem-catalogue.md for how every declaration here was derived.
 *
 *****************************************************************************/
#ifndef __EZ_WIFI_H__
#define __EZ_WIFI_H__

/* The 802.11 element the smart-config protocol rides on.  Two EIDs are in
 * use: 207 for the original scheme and 208 ("eid208") for the newer one. */
#define EZ_SYNC_CODE_LEN	5
#define EZ_VALUE_LEN		32

struct ez_probe_t {
	u8	element;
	u8	element_len;
	u8	sync[EZ_SYNC_CODE_LEN];
	u16	id;
	u8	len;
	u8	value[EZ_VALUE_LEN];
} __attribute__((packed));		/* 42 bytes */

/* what the smart-config ioctl exchanges with user space */
#define EZ_NEW_SC_BUF_LEN	512

struct ez_new_sc_t {
	u8	enable;
	u8	done;
	u8	buf[EZ_NEW_SC_BUF_LEN];
	u16	len;
};					/* 516 bytes */

struct ez_scan_cmd_t {
	u8	cmd;
	u8	len;
	u8	value[EZ_VALUE_LEN];
};					/* 34 bytes */

/* ez_new_sc ioctl sub-commands */
#define NEW_SC_INIT		0
#define NEW_SC_DEINIT		1
#define NEW_SC_POLL_RESULT	2
#define NEW_SC_GET_RESULTS	3
#define NEW_SC_SET_REASON	4

/* ez_scan_device ioctl sub-commands */
#define SCAN_IDLE		0
#define TRIG_SCAN_DEVICE	1
#define POLL_DEVICE		2
#define TRIG_SCAN_REASON	3
#define POLL_REASON		4

#define EZ_DEVICE_SN_LEN	9
#define EZ_DEVICE_INFO_LEN	41

extern struct ez_new_sc_t ez_new_sc;
extern struct ez_probe_t probe_req_t;
extern struct ez_probe_t probe_resp_t;
extern u8 DeviceInfo[EZ_DEVICE_INFO_LEN];
extern u8 null_sn[EZ_DEVICE_SN_LEN];
extern u8 smart_flg;
extern u8 scan_flag;

/* ez_sc.c */
void hexdump(u8 *buf, int len);
char ez_set_join_fail_reason(char result);
int ez_get_join_fail_reason(void);
int set_smartconfig_flag(u8 flag);
int check_scan_flag(void);
int set_scan_flag(int flag);
int rtw_ezviz_ie_set(_adapter *padapter, u32 vendor_ie_mask, u8 *ie, u32 ielen);
int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_new_sc_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_device_info_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_probe_req_handler(u8 *pframe, int len);
int ez_probe_response_eid208_handler(u8 *pframe, int len);
int ez_probe_requst_eid208_handler(u8 *pframe, int len);

/* ez_wifi_config.c */
void ez_wifi_preinit(void);
int ez_read_rssi_per_ant_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_wifi_func_poll_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_wifi_module_rf_calibration_check_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);

/* the EZVIZ private ioctl numbers, dispatched from rtw_ioctl() */
#define EZ_NEW_SMART_CONFIG_IO		0x8BF5
#define EZ_IOCTL_READ_RSSI_PER_ANT	0x8BFB
#define EZ_IOCTL_SET_NEW_SC		0x8C05
#define EZ_IOCTL_DEVINFO_IO		0x8C07
#define EZ_IOCTL_SCAN_IO		0x8C08
#define EZ_IOCTL_WIFI_FUNC_POLL		0x8C09
#define EZ_IOCTL_RF_CALIBRATION_CHECK	0x8C0B

#endif /* __EZ_WIFI_H__ */
