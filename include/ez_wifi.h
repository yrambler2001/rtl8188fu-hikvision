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

/* the 4-byte sub-element ez_probe_requst_eid208_handler() appends */
struct ez_tlv_t {
	u16	id;
	u8	len;
	u8	value;
};					/* 4 bytes */

struct ez_scan_cmd_t {
	u8	cmd;
	u8	len;
	u8	value[EZ_VALUE_LEN];
};					/* 34 bytes */

#define EZ_DEVICE_SN_LEN	9
#define EZ_DEVICE_INFO_LEN	41

extern struct ez_new_sc_t ez_new_sc;
extern struct ez_probe_t probe_req_t;
extern struct ez_probe_t probe_resp_t;
extern u8 DeviceInfo[EZ_DEVICE_INFO_LEN];
extern u8 null_sn[EZ_DEVICE_SN_LEN];
extern u8 smart_flg;
extern u8 scan_flag;

void hexdump(u8 *buf, int len);

#endif /* __EZ_WIFI_H__ */
