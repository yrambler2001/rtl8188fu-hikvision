/******************************************************************************
 *
 * ez_wifi_config.c -- EZVIZ per-unit configuration: /home/config.txt parsing
 * (MAC address and country code), efuse readback, and the RSSI / version /
 * RF-calibration private ioctls.
 *
 * Reconstructed from the shipped 8188fu.ko; not part of any public Realtek
 * release.  See FINDINGS-oem-catalogue.md.
 *
 *****************************************************************************/
#define _EZ_WIFI_CONFIG_C_

#include <drv_types.h>
#include <hal_data.h>
#include "../../hal/phydm/phydm_precomp.h"
#include <ez_wifi.h>

/* module parameters, defined in os_dep/linux/os_intfs.c */
extern int rtw_channel_plan;
extern char *rtw_initmac;

#define EZ_CONFIG_FILE		"/home/config.txt"
#define EZ_CONFIG_BUF_SIZE	4096
#define EZ_PICK_BUF_SIZE	1024

#define EZ_WIFI_SOC_PLATFORM	"M377"
#define EZ_WIFI_CHIP		"rtl8188s"
#define EZ_WIFI_VERSION		"-SN215081-Release_231225"

/* efuse map addresses */
#define EZ_EFUSE_MAC_ADDR		0xD7
#define EZ_EFUSE_MAC_LEN		6
#define EZ_RF_POWER_INIDEX_ADDR		0x10
#define EZ_RF_POWER_INIDEX_LEN		12
#define EZ_RF_CRYSTAL_CALIBRATION	0xB9
#define EZ_RF_CRYSTAL_THERMAL_METER	0xBA

static char us_country_code_table[][3] = {
	"US", "CA", "MX", "TW", "VI", "DO", "GT"
};

static char br_country_code_table[][3] = {
	"BR", "CO", "BB", "CR", "EC", "UY", "BM", "DM", "GY", "HT", "TT", "NI",
	"HN", "PA", "VE", "PY", "BS", "FM", "GD", "JM", "PW", "SV", "VU", "CL",
	"AR", "IN", "PK"
};

static char etsi_country_code_table[][3] = {
	"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB",
	"GR", "HR", "HU", "IE", "IT", "LU", "MT", "NL", "PL", "PT", "RO", "SE",
	"SI", "SK", "TR", "LV", "LT", "KW", "KZ", "LB", "AD", "AM", "AZ", "BD",
	"GE", "HK", "KG", "LK", "MD", "MN", "MP", "MR", "NA", "PG", "TD", "TJ",
	"TM", "UZ", "ZW", "IR", "OM", "SG", "TH", "VN", "ZA", "JO", "BY", "RU",
	"IL", "SA", "IQ", "AG", "AL", "AO", "BA", "BJ", "BZ", "CH", "CM", "CV",
	"FJ", "GA", "IS", "KH", "KI", "KN", "LA", "LC", "LI", "LY", "MC", "MK",
	"ML", "MO", "MV", "MZ", "NO", "NP", "RS", "SC", "SM", "SN", "SZ", "TG",
	"TN", "TZ", "UG", "VA", "VC", "WS", "YE", "ZM", "AU", "MY", "PH", "ID",
	"AE", "KR", "NZ", "KE", "LS", "EG", "UA", "MA", "QA", "EU"
};

static char eu_country_code_table[][3] = {
	"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB",
	"GR", "HR", "HU", "IE", "IT", "LU", "MT", "NL", "PL", "PT", "RO", "SE",
	"SI", "SK", "TR", "LV", "LT", "EU", "NO", "AD", "CH", "IS", "MC", "MK"
};

static char apec_country_code_table[][3] = {
	"KW", "KZ", "LB", "AD", "AM", "AZ", "BD", "GE", "HK", "KG", "LK", "MD",
	"MN", "MP", "MR", "NA", "PG", "TD", "TJ", "TM", "UZ", "ZW", "IR", "OM",
	"SG", "TH", "VN", "ZA", "JO", "BY", "RU", "IL", "SA", "IQ", "AG", "AL",
	"AO", "BA", "BJ", "BZ", "CH", "CM", "CV", "FJ", "GA", "IS", "KH", "KI",
	"KN", "LA", "LC", "LI", "LY", "MC", "MK", "ML", "MO", "MV", "MZ", "NO",
	"NP", "RS", "SC", "SM", "SN", "SZ", "TG", "TN", "TZ", "UG", "VA", "VC",
	"WS", "YE", "ZM", "AU", "MY", "PH", "ID", "AE", "KR"
};

static char jp_country_code_table[][3] = {
	"JP"
};

static char other_country_code_table[][3] = {
	"CN", "AF", "BF", "BH", "BI", "BN", "BO", "BT", "BW", "CD", "CF", "CG",
	"CI", "CK", "CU", "DJ", "DZ", "ER", "ET", "GH", "GM", "GN", "GQ", "GW",
	"KM", "KP", "LR", "MG", "MH", "MM", "MU", "NE", "NG", "NR", "NU", "PS",
	"RW", "SB", "SD", "SL", "SO", "ST", "SY", "TO", "TP", "TV"
};

u8 ez_mac_addr[17];

const u8 invalid_efuse_data1[10] = {
	0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff
};

const u8 invalid_efuse_data2[10] = {
	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

int process_config_vars(char *buf, u32 len, char *pick, const char *var)
{
	u32 i;
	int j = 0;
	int m = 0;
	int n = 0;
	int end = 0;
	int pos = 0;

	for (i = 0; i < len; i++) {
		if (buf[i] == '\r')
			continue;

		if (pos || n) {
			if (buf[i] == '\n') {
				if (n) {
					n = 0;
					pos = 0;
				} else {
					pos = 0;
					end = 0;
				}
			}
			continue;
		}

		switch (buf[i]) {
		case '#':
			n |= pos;
			pos = 1;
			continue;
		case '\\':
			n = 1;
			break;
		case '\n':
			end = pos | n;
			n |= pos;
			break;
		default: {
			size_t vlen = strlen(var);

			if (end || memcmp(&buf[i], var, vlen)) {
				int skip;

				if (end)
					skip = 0;
				else
					skip = m & 1;
				if (skip) {
					end = 0;
					m = 0;
					break;
				}
				end++;
				if (!m)
					break;
			} else {
				end = vlen;
				j = 0;
				i += vlen;
			}
			if (buf[i] != '\t') {
				if (j) {
					int last = pick[j - 1];

					m = (last == ' ' && buf[i] == ' ');
					if (m)
						break;
				}
				pick[j++] = buf[i];
			}
			m = 1;
			break;
		}
		}
		pos = 0;
	}

	return j;
}

int ez_os_get_image_block(char *buffer, u32 size, struct file *fp)
{
	int ret;

	if (fp == NULL)
		return 0;

	ret = kernel_read(fp, buffer, size, &fp->f_pos);
	if (ret > 0)
		fp->f_pos += ret;

	return ret;
}

struct file *ez_os_open_image(const char *filename)
{
	struct file *fp;

	printk("filename: %s\n", filename);

	fp = filp_open(filename, O_RDONLY, 0);
	if (IS_ERR(fp))
		return NULL;

	return fp;
}

void ez_os_close_image(struct file *fp)
{
	if (fp)
		filp_close(fp, NULL);
}

int woal_is_us_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(us_country_code_table) / sizeof(us_country_code_table[0]); i++) {
		if (!memcmp(country_code, us_country_code_table[i], 2)) {
			printk("found region code=%s in US table.\n", us_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_br_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(br_country_code_table) / sizeof(br_country_code_table[0]); i++) {
		if (!memcmp(country_code, br_country_code_table[i], 2)) {
			printk("found region code=%s in BR table.\n", br_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_etsi_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(etsi_country_code_table) / sizeof(etsi_country_code_table[0]); i++) {
		if (!memcmp(country_code, etsi_country_code_table[i], 2)) {
			printk("found region code=%s in ETSI table\n", etsi_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_eu_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(eu_country_code_table) / sizeof(eu_country_code_table[0]); i++) {
		if (!memcmp(country_code, eu_country_code_table[i], 2)) {
			printk("found region code=%s in EU table\n", eu_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_apec_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(apec_country_code_table) / sizeof(apec_country_code_table[0]); i++) {
		if (!memcmp(country_code, apec_country_code_table[i], 2)) {
			printk("found region code=%s in APEC table\n", apec_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_jp_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(jp_country_code_table) / sizeof(jp_country_code_table[0]); i++) {
		if (!memcmp(country_code, jp_country_code_table[i], 2)) {
			printk("found region code=%s in JP table.\n", jp_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

int woal_is_other_country(char *country_code)
{
	int i;

	for (i = 0; i < sizeof(other_country_code_table) / sizeof(other_country_code_table[0]); i++) {
		if (!memcmp(country_code, other_country_code_table[i], 2)) {
			printk("found region code=%s in other table.\n", other_country_code_table[i]);
			return 1;
		}
	}

	return 0;
}

void ez_set_country(char *country_code)
{
	int chplan;

	if (!country_code) {
		RTW_ERR("%s country_code is NULL !!! \n", __FUNCTION__);
		return;
	}

	if (woal_is_us_country(country_code)) {
		chplan = 0x43;
	} else if (woal_is_eu_country(country_code)) {
		chplan = 0x42;
	} else if (woal_is_jp_country(country_code)) {
		chplan = 0x37;
	} else {
		RTW_ERR("%s country_code:%s,use default channel plan set . \n",
			__FUNCTION__, country_code);
		chplan = 0x62;
	}

	rtw_channel_plan = chplan;

	RTW_ERR("##%s :: country_code:%s\n", __func__, country_code);
}

void ez_wifi_version_info(void)
{
	printk("soc platform:%s\r\n", EZ_WIFI_SOC_PLATFORM);
	printk("wifi chip:%s\r\n", EZ_WIFI_CHIP);
	printk("wifi version:%s\r\n", EZ_WIFI_VERSION);
	printk("build time:%s  %s\r\n", __DATE__, __TIME__);
}

struct ez_rssi_per_ant {
	u8	Valid;
	s8	Rssi_ANT0;
	s8	Rssi_ANT1;
	s8	Rssi_AVG;
};

int ez_read_rssi_per_ant_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
	_adapter *padapter;
	struct iwreq *wrq = (struct iwreq *)rq;
	HAL_DATA_TYPE *pHalData;
	struct dm_struct *pDM_Odm;
	struct recv_priv *precvpriv;
	struct ez_rssi_per_ant rssi;

	printk("\n ####### ez_read_rssi_per_ant_ioctl ENTER  , cmd = %x\n", cmd);

	if (!dev || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return -1;
	}

	if (!wrq->u.data.pointer) {
		printk("iwp == NULL or iwp->pointer == null!!!\n");
		return -1;
	}

	padapter = (_adapter *)rtw_netdev_priv(dev);
	precvpriv = &padapter->recvpriv;
	pHalData = GET_HAL_DATA(padapter);
	pDM_Odm = &pHalData->odmpriv;

	memset(&rssi, 0, sizeof(rssi));

	printk("RxRate = %s, RSSI_A = %d(%%), RSSI_B = %d(%%)\n",
	       HDATA_RATE(pDM_Odm->rx_rate), pDM_Odm->rssi_a, pDM_Odm->rssi_b);

	rssi.Valid = 1;
	rssi.Rssi_AVG = precvpriv->rssi;
	rssi.Rssi_ANT0 = pDM_Odm->rssi_a - 100;
	rssi.Rssi_ANT1 = pDM_Odm->rssi_a - 100;

	printk("rssi.Valid = %d, RxRate = %s, Rssi_ANT0 = %d(%%), Rssi_ANT1 = %d(%%), rssi.Rssi_AVG = %d\n",
	       rssi.Valid, HDATA_RATE(pDM_Odm->rx_rate), rssi.Rssi_ANT0, rssi.Rssi_ANT1,
	       rssi.Rssi_AVG);

	return copy_to_user(wrq->u.data.pointer, &rssi, sizeof(rssi));
}

int ez_hexval(char c)
{
	if (c >= '0' && c <= '9')
		return c - '0';
	if (c >= 'A' && c <= 'F')
		return c - 'A' + 10;
	if (c >= 'a' && c <= 'f')
		return c - 'a' + 10;

	return 0;
}

int ez_atox(char *s)
{
	int val = 0;

	while ((*s >= '0' && *s <= '9')
	       || ((*s & ~0x20) >= 'A' && (*s & ~0x20) <= 'F')) {
		val = val * 16 + ez_hexval(*s);
		s++;
	}

	return val;
}

char *ez_strsep(char **stringp, char delim, char esc)
{
	char *s = *stringp;
	char *p;
	char c;

	if (s == NULL)
		return s;

	if (*s == '\0')
		return (char *)(unsigned char)*s;

	p = s;
	for (;;) {
		c = *p++;
		if (c == '\0')
			break;
		if (c == esc && (*p == esc || *p == delim)) {
			memmove(p - 1, p, strlen(p - 1));
		} else if (c == delim) {
			p[-1] = '\0';
			break;
		}
	}
	*stringp = p;

	return s;
}

int ez_mac2u8(u8 *mac, const char *s, char *end)
{
	char *sep;
	char *buf;
	char *p = NULL;
	int i = 0;

	if (!s)
		return 0;

	buf = kmalloc(strlen(s) + 1, GFP_KERNEL);
	if (!buf)
		return 0;

	memcpy(buf, s, strlen(s));
	p = buf;

	do {
		sep = ez_strsep(&p, ':', '/');
		if (sep)
			mac[i] = ez_atox(sep);
		i++;
	} while (i != 6);

	kfree(buf);

	return 0;
}

int ez_get_mac_addr(void)
{
	struct file *fp;
	char *buf = NULL;
	char *pick = NULL;
	int len;
	int ret = 0;

	fp = ez_os_open_image(EZ_CONFIG_FILE);
	if (!fp) {
		RTW_ERR("%s: open config file failed %s\n", __FUNCTION__, EZ_CONFIG_FILE);
		return -1;
	}

	buf = kmalloc(EZ_CONFIG_BUF_SIZE, GFP_KERNEL);
	if (!buf) {
		RTW_ERR("%s: Failed to allocate memory %d bytes\n", __FUNCTION__,
			EZ_CONFIG_BUF_SIZE);
		ret = -1;
		goto close;
	}

	pick = kmalloc(EZ_PICK_BUF_SIZE, GFP_KERNEL);
	if (!pick) {
		RTW_ERR("%s: Failed to allocate memory %d bytes\n", __FUNCTION__,
			EZ_PICK_BUF_SIZE);
		ret = -1;
		goto free_buf;
	}

	len = ez_os_get_image_block(buf, EZ_CONFIG_BUF_SIZE, fp);
	if (len <= 0 || len >= EZ_CONFIG_BUF_SIZE) {
		RTW_ERR("%s: error reading config file: %d,use default mac addr and countrycode: CN \n",
			__FUNCTION__, len);
		ret = -1;
	} else {
		int n;

		ret = 0;
		buf[len] = '\0';
		memset(pick, 0, EZ_PICK_BUF_SIZE);
		n = process_config_vars(buf, len, pick, "mac_addr=");
		if (n == 17) {
			memset(ez_mac_addr, 0, sizeof(ez_mac_addr));
			memcpy(ez_mac_addr, pick, 17);
			ret = 0;
			rtw_initmac = ez_mac_addr;
			printk("%s: pick=%s,rtw_initmac:%s, len=%d\n", __FUNCTION__, pick,
			       ez_mac_addr, n);
		} else {
			RTW_ERR("%s: the length is bad :%d! \n", __FUNCTION__, n);
		}
	}

	kfree(pick);
free_buf:
	kfree(buf);
close:
	ez_os_close_image(fp);

	return ret;
}

void ez_wifi_preinit(void)
{
	struct file *fp = NULL;
	char *buf = NULL;
	char *pick = NULL;
	char *ccode;
	int len;
	int ret = 0;

	printk("%s: enter\n", __func__);

	fp = ez_os_open_image(EZ_CONFIG_FILE);
	if (!fp) {
		RTW_ERR("%s: Ignore config file %s\n", __FUNCTION__, EZ_CONFIG_FILE);
		ret = -1;
		goto set_default;
	}

	buf = kmalloc(EZ_CONFIG_BUF_SIZE, GFP_KERNEL);
	if (!buf) {
		RTW_ERR("%s: Failed to allocate memory %d bytes\n", __FUNCTION__,
			EZ_CONFIG_BUF_SIZE);
		ret = -1;
		goto set_default;
	}

	pick = kmalloc(EZ_PICK_BUF_SIZE, GFP_KERNEL);
	if (!pick) {
		RTW_ERR("%s: Failed to allocate memory %d bytes\n", __FUNCTION__,
			EZ_PICK_BUF_SIZE);
		ret = -1;
		goto set_default;
	}

	len = ez_os_get_image_block(buf, EZ_CONFIG_BUF_SIZE, fp);
	if (len <= 0 || len >= EZ_CONFIG_BUF_SIZE) {
		RTW_ERR("%s: error reading config file,set default countrycode: CN \n",
			__FUNCTION__);
		ret = -1;
		goto version;
	}

	buf[len] = '\0';
	memset(pick, 0, EZ_PICK_BUF_SIZE);
	len = process_config_vars(buf, len, pick, "ccode=");
	if (!len) {
		RTW_ERR("%s: error file content=%d\n", __FUNCTION__, 0);
		ret = -1;
		goto version;
	}

	ccode = pick;
	if (len != 2) {
		RTW_ERR("%s: the countrycode length is bad ! \n", __FUNCTION__);
		ccode = "CN";
	}
	RTW_ERR("%s: pick=%s,len=%d\n", __FUNCTION__, ccode, len);
	ret = 0;
	ez_set_country(ccode);

version:
	ez_wifi_version_info();
	ez_get_mac_addr();
	if (!ret)
		goto free_pick;

set_default:
	ret = -1;
	ez_set_country("CN");
	if (!pick)
		goto free_buf;

free_pick:
	kfree(pick);
free_buf:
	if (buf)
		kfree(buf);
	if (fp)
		ez_os_close_image(fp);
}

int ez_GetMaskBit(void)
{
	printk("maskbit:0x%x\r\n", 0x9F);
	return 0x9F;
}

int ez_GetWiFiVersion(char *version)
{
	u32 maskbit = ez_GetMaskBit();

	switch (maskbit) {
	case 0x00:
	case 0x80:
		strcpy(version, "0.0.0_");
		break;
	case 0x87:
		strcpy(version, "1.0.0_");
		break;
	case 0x8F:
		strcpy(version, "1.0.1_");
		break;
	case 0x97:
		strcpy(version, "1.0.2_");
		break;
	case 0x9F:
		strcpy(version, "1.0.3_");
		break;
	default:
		return 0;
	}

	strcat(version, EZ_WIFI_VERSION);

	return 0;
}

int ez_wifi_func_poll_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
	struct iwreq *wrq = (struct iwreq *)rq;
	char version[32];
	u32 len;
	int ret;

	memset(version, 0, sizeof(version));

	printk("\n ####### %s() Enter, cmd = %x\n", __func__, cmd);

	if (!dev || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return -1;
	}

	if (!wrq->u.data.pointer) {
		printk("iwp == NULL or iwp->pointer == null!!!\n");
		return -1;
	}

	ez_GetWiFiVersion(version);

	len = wrq->u.data.length;
	if (len < strlen(version))
		ret = copy_to_user(wrq->u.data.pointer, version, (u8)len);
	else
		ret = copy_to_user(wrq->u.data.pointer, version, (u8)strlen(version));

	printk("version:%s, strlen:%d, ret:%d\n", version, strlen(version), ret);

	return ret;
}

int ez_read_efuse(PADAPTER padapter, u16 addr, u16 cnts, u8 *data)
{
	if (!data) {
		RTW_ERR("ez_read_efuse param is null\n");
		return -1;
	}

	if (!rtw_efuse_mask_map_read(padapter, addr, cnts, data)) {
		RTW_INFO("%s: rtw_efuse_mask_map_read error!\n", __func__);
		return -1;
	}

	return 0;
}

int ez_read_efuse_mac(PADAPTER padapter)
{
	u8 efuse_mac[EZ_EFUSE_MAC_LEN];
	int ret;

	memset(efuse_mac, 0, EZ_EFUSE_MAC_LEN);

	ret = ez_read_efuse(padapter, EZ_EFUSE_MAC_ADDR, EZ_EFUSE_MAC_LEN, efuse_mac);
	if (ret) {
		RTW_ERR("ez_read_efuse error\n");
		return -1;
	}

	if (!memcmp(efuse_mac, invalid_efuse_data1, EZ_EFUSE_MAC_LEN)
	    || !memcmp(efuse_mac, invalid_efuse_data2, EZ_EFUSE_MAC_LEN)) {
		RTW_ERR("efuse_mac is invalid!!\r\n");
		return -1;
	}

	RTW_INFO("efuse MAC: =%02x:%02x:%02x:%02x:%02x:%02x\n", efuse_mac[0], efuse_mac[1],
		 efuse_mac[2], efuse_mac[3], efuse_mac[4], efuse_mac[5]);

	return ret;
}

int ez_read_efuse_rf(PADAPTER padapter)
{
	u8 efuse_rf_data[EZ_RF_POWER_INIDEX_LEN];
	u8 crystal_cali = 0xFF;
	u8 thermal_meter = 0xFF;
	int i;
	int ret;

	memset(efuse_rf_data, 0xFF, EZ_RF_POWER_INIDEX_LEN);

	ret = ez_read_efuse(padapter, EZ_RF_POWER_INIDEX_ADDR, EZ_RF_POWER_INIDEX_LEN,
			    efuse_rf_data);
	if (ret) {
		RTW_ERR("ez_read_efuse error\n");
		return -1;
	}

	for (i = 0; i < EZ_RF_POWER_INIDEX_LEN; i++) {
		if (efuse_rf_data[i] == 0xFF) {
			RTW_ERR("efuse_rf_data RF_POWER_INIDEX_ADDR err %d %x \n", i,
				efuse_rf_data[i]);
			return -1;
		}
	}

	ret = ez_read_efuse(padapter, EZ_RF_CRYSTAL_CALIBRATION, 1, &crystal_cali);
	if (ret) {
		RTW_ERR("ez_read_efuse error\n");
		return -1;
	}

	if (crystal_cali == 0xFF) {
		RTW_ERR("RF_CRYSTAL_CALIBRATION error\n");
		return -1;
	}

	ret = ez_read_efuse(padapter, EZ_RF_CRYSTAL_THERMAL_METER, 1, &thermal_meter);
	if (ret) {
		RTW_ERR("ez_read_efuse error\n");
		return -1;
	}

	if (thermal_meter == 0xFF) {
		RTW_ERR("RF_CRYSTAL_THERMAL_METER error\n");
		return -1;
	}

	return ret;
}

int ez_read_eFuse_free_block(PADAPTER padapter)
{
	u16 cur_size = 0;
	int max_size;

	efuse_GetCurrentSize(padapter, &cur_size);
	max_size = efuse_GetMaxSize(padapter);

	RTW_DBG("[available raw size]= %d bytes\n", max_size - cur_size);

	if (max_size - cur_size <= 0)
		return -1;

	return 0;
}

int ez_wifi_module_rf_calibration_check_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
	_adapter *padapter;
	struct iwreq *wrq = (struct iwreq *)rq;
	int efuse_mac_ret, efuse_rf_ret, free_block_ret;
	int rf_calibration_check_ret = -1;
	int ret = -1;

	padapter = (_adapter *)rtw_netdev_priv(dev);

	printk("\n ####### ez_wifi_module_rf_check_ioctl ENTER  , cmd = %x\n", cmd);

	if (!padapter || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return ret;
	}

	if (!wrq->u.data.pointer) {
		printk("iwp == NULL or iwp->pointer == null!!!\n");
		return ret;
	}

	efuse_mac_ret = ez_read_efuse_mac(padapter);
	efuse_rf_ret = ez_read_efuse_rf(padapter);
	free_block_ret = ez_read_eFuse_free_block(padapter);

	if (efuse_mac_ret == -1 && efuse_rf_ret == -1)
		rf_calibration_check_ret = 3;
	else if (efuse_rf_ret == -1)
		rf_calibration_check_ret = 2;
	else if (efuse_mac_ret == -1)
		rf_calibration_check_ret = 1;
	else
		rf_calibration_check_ret = 0;

	if (free_block_ret == -1)
		rf_calibration_check_ret = 4;

	ret = copy_to_user(wrq->u.data.pointer, &rf_calibration_check_ret, 4);
	printk("rf_calibration_check_ret == %d\n", rf_calibration_check_ret);

	return ret;
}
