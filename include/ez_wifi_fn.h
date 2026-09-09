/******************************************************************************
 *
 * Prototypes for the OEM (EZVIZ / Hikvision) translation units ez_sc.c and
 * ez_wifi_config.c.  Kept out of <ez_wifi.h> - which drv_types.h pulls into
 * every translation unit - and included only where these functions are
 * called.  That split is not a style choice: the shipped module's DECL_UID
 * uniquifiers (__func__.NNNN in .strtab) pin how many declarations each
 * translation unit sees, and they only come out right this way.  See
 * FINDINGS-oem-catalogue.md section 11.
 *
 *****************************************************************************/
#ifndef __EZ_WIFI_FN_H__
#define __EZ_WIFI_FN_H__

/* ez_new_sc ioctl sub-commands */
enum ez_new_sc_cmd {
	NEW_SC_INIT		= 0,
	NEW_SC_DEINIT		= 1,
	NEW_SC_POLL_RESULT	= 2,
	NEW_SC_GET_RESULTS	= 3,
	NEW_SC_SET_REASON	= 4,
};

/* ez_scan_device ioctl sub-commands */
enum ez_scan_cmd {
	SCAN_IDLE		= 0,
	TRIG_SCAN_DEVICE	= 1,
	POLL_DEVICE		= 2,
	TRIG_SCAN_REASON	= 3,
	POLL_REASON		= 4,
};

/* the EZVIZ private ioctl numbers, dispatched from rtw_ioctl() */
enum ez_ioctl_cmd {
	EZ_NEW_SMART_CONFIG_IO		= 0x8BF5,
	EZ_IOCTL_READ_RSSI_PER_ANT	= 0x8BFB,
	EZ_IOCTL_SET_NEW_SC		= 0x8C05,
	EZ_IOCTL_DEVINFO_IO		= 0x8C07,
	EZ_IOCTL_SCAN_IO		= 0x8C08,
	EZ_IOCTL_WIFI_FUNC_POLL		= 0x8C09,
	EZ_IOCTL_RF_CALIBRATION_CHECK	= 0x8C0B,
};

/* The shipped module's DECL_UID uniquifiers (the __func__.NNNN suffixes in
 * .strtab) pin how many declarations this header contributed to the vendor's
 * build: five more than the API that can be recovered from the binary.  A
 * declaration whose definition was never linked in leaves no other trace, so
 * what those five were cannot be recovered - only how many there were.  This
 * enum stands in for them.  Drop it and every __func__.NNNN in ioctl_linux.c
 * and rtw_mlme_ext.c shifts by five and .strtab stops matching. */
enum ez_unrecovered {
	EZ_UNRECOVERED_0,
	EZ_UNRECOVERED_1,
	EZ_UNRECOVERED_2,
	EZ_UNRECOVERED_3,
};

/* ez_sc.c */
char ez_set_join_fail_reason(char result);
int ez_get_join_fail_reason(void);
int set_smartconfig_flag(u8 flag);
int check_scan_flag(void);
int set_scan_flag(int flag);
int ez_set_new_sc(struct net_device *dev, int cmd, struct iw_point *iwp);
int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);
int rtw_ezviz_ie_set(_adapter *padapter, u32 vendor_ie_mask, u8 *ie, u32 ielen);
int ez_new_sc_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_device_info_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int check_sn_valid(void);
int check_probe_sync_EID(u8 *buf, int len);
int ez_probe_req_handler(u8 *pframe, int len);
int check_probe_sync_eid208(u8 *buf, int len);
int ez_probe_response_eid208_handler(u8 *pframe, int len);
int ez_probe_requst_eid208_handler(u8 *pframe, int len);
int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);

/* ez_wifi_config.c */
int process_config_vars(char *buf, u32 len, char *pick, const char *var);
int ez_os_get_image_block(char *buffer, u32 size, struct file *fp);
struct file * ez_os_open_image(const char *filename);
void ez_os_close_image(struct file *fp);
int woal_is_us_country(char *country_code);
int woal_is_br_country(char *country_code);
int woal_is_etsi_country(char *country_code);
int woal_is_eu_country(char *country_code);
int woal_is_apec_country(char *country_code);
int woal_is_jp_country(char *country_code);
int woal_is_other_country(char *country_code);
void ez_set_country(char *country_code);
void ez_wifi_version_info(void);
int ez_read_rssi_per_ant_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_hexval(char c);
int ez_atox(char *s);
char * ez_strsep(char **stringp, char delim, char esc);
void ez_mac2u8(u8 *mac, const char *s, char *end);
int ez_get_mac_addr(void);
int ez_wifi_preinit(void);
u32 ez_GetMaskBit(void);
int ez_GetWiFiVersion(char *version);
int ez_wifi_func_poll_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd);
int ez_read_efuse(PADAPTER padapter, u16 addr, u16 cnts, u8 *data);
int ez_read_efuse_mac(PADAPTER padapter);
int ez_read_efuse_rf(PADAPTER padapter);
int ez_read_eFuse_free_block(PADAPTER padapter);
int ez_wifi_module_rf_calibration_check_ioctl(struct net_device *dev, struct ifreq *rq, int cmd);

#endif /* __EZ_WIFI_FN_H__ */
