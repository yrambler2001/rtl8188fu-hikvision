/******************************************************************************
 *
 * ez_sc.c -- EZVIZ smart-config / device-discovery over 802.11 probe frames.
 *
 * Reconstructed from the shipped 8188fu.ko; not part of any public Realtek
 * release.  See FINDINGS-oem-catalogue.md.
 *
 *****************************************************************************/
#define _EZ_SC_C_

#include <drv_types.h>
#include <ez_wifi.h>
#include <ez_wifi_fn.h>

static s8 err_status;
u8 smart_flg;
u8 scan_flag;
struct ez_new_sc_t ez_new_sc;
u8 DeviceInfo[EZ_DEVICE_INFO_LEN];
u8 null_sn[EZ_DEVICE_SN_LEN];
struct ez_probe_t probe_resp_t;
struct ez_probe_t probe_req_t;

static char ez_sync_code[EZ_SYNC_CODE_LEN] = "EZVIZ";

char ez_set_join_fail_reason(char result)
{
	err_status = result;
	return result;
}

int ez_get_join_fail_reason(void)
{
	return err_status;
}

int set_smartconfig_flag(u8 flag)
{
	smart_flg = flag;
	return 0;
}

int check_scan_flag(void)
{
	return scan_flag;
}

int check_probe_sync_EID(u8 *buf, int len)
{
	int sn_valid = check_sn_valid();
	int i;

	printk("\n  check_probe_sync_EID enter,sn_valid:%d! \n", sn_valid);

	if (!buf) {
		printk("check_probe_sync_EID input buf if NULL!\n");
		return -1;
	}

	for (i = 0; i < len - 2; i += buf[i + 1] + 2) {
		if (sn_valid) {
			if ((buf[i] == 207 || buf[i] == 209)
			    && !memcmp(&buf[i + 2], ez_sync_code, EZ_SYNC_CODE_LEN)) {
				printk("\n %s: get ez_sync_code,suport 207 or 209! \n\r", __func__);
				return i;
			}
		} else {
			if (buf[i] == 207
			    && !memcmp(&buf[i + 2], ez_sync_code, EZ_SYNC_CODE_LEN)) {
				printk("\n %s: get ez_sync_code,only suport 207 \n\r", __func__);
				return i;
			}
		}
	}

	return 0;
}

int set_scan_flag(int flag)
{
	scan_flag = flag ? 1 : 0;
	return 0;
}

void hexdump(u8 *buf, int len)
{
	u8 *p;

	printk("-------------kernel hexdump start--------------\n");
	for (p = buf; p != buf + len; p++) {
		printk("%2x ", *p);
		if (((p + 1 - buf) % 16) == 0)
			printk("\n");
	}
	printk("\n");
	printk("-------------kernel hexdump end--------------\n");
}

int ez_set_new_sc(struct net_device *dev, int cmd, struct iw_point *iwp)
{
	int ret = 0;
	u32 addr = 0;
	int sc_cmd[2];
	u8 buf[514];

	memset(buf, 0, 514);

	if (copy_from_user(sc_cmd, iwp->pointer, 8)) {
		ret = -EFAULT;
		goto exit;
	}

	switch (sc_cmd[0]) {
	case NEW_SC_INIT:
		printk("cmd NEW_SC_INIT\n");
		memset(&ez_new_sc, 0, sizeof(ez_new_sc));
		ez_new_sc.enable = 1;
		err_status = 0;
		break;
	case NEW_SC_DEINIT:
		ret = 0;
		printk("cmd NEW_SC_DEINIT\n");
		memset(&ez_new_sc, 0, sizeof(ez_new_sc));
		err_status = 0;
		break;
	case NEW_SC_POLL_RESULT:
		printk("cmd NEW_SC_POLL_RESULT\n");
		if (!ez_new_sc.done)
			ret = 0;
		else
			ret = 308;
		ez_new_sc.done = 0;
		break;
	case NEW_SC_GET_RESULTS:
		printk("cmd NEW_SC_GET_RESULTS\n");
		ret = copy_from_user(&addr, (u8 *)iwp->pointer + 4, 4);
		ret |= copy_to_user((void *)(addr + 8), ez_new_sc.buf, ez_new_sc.len);
		ret |= copy_to_user((void *)addr, &ez_new_sc.len, 2);
		ez_new_sc.done = 0;
		break;
	case NEW_SC_SET_REASON:
		printk("cmd NEW_SC_SET_REASON\n");
		ret = copy_from_user(&addr, (u8 *)iwp->pointer + 4, 4);
		ret |= copy_from_user(buf, (void *)addr, 8);
		err_status = buf[2];
		break;
	default:
		ret = -EINVAL;
		printk("cmd invalid\n");
		break;
	}

exit:
	return ret;
}

int ez_new_sc_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)
{
	struct iwreq *wrq = (struct iwreq *)rq;
	int is_null = (dev == NULL || rq == NULL);

	if (is_null) {
		printk("ez_new_sc_ioctl input param is NULL!\n");
		return -1;
	}

	return ez_set_new_sc(dev, is_null, &wrq->u.data);
}

int rtw_ezviz_ie_set(_adapter *padapter, u32 vendor_ie_mask, u8 *ie, u32 ielen)
{
	int ret = 0;
	struct mlme_priv *pmlmepriv = &(padapter->mlmepriv);

	if (vendor_ie_mask == 0) {
		RTW_INFO("[%s] Clear vendor_ie_num %d group\n", __func__, 0);
		goto _clear_path;
	}

	_rtw_memcpy(pmlmepriv->vendor_ie[0], ie, ielen);
	pmlmepriv->vendor_ielen[0] = ielen;

	if (vendor_ie_mask & WIFI_BEACON_VENDOR_IE_BIT)
		RTW_INFO("[%s] Beacon append vendor ie\n", __func__);
	if (vendor_ie_mask & WIFI_PROBEREQ_VENDOR_IE_BIT)
		RTW_INFO("[%s] Probe Req append vendor ie\n", __func__);
	if (vendor_ie_mask & WIFI_PROBERESP_VENDOR_IE_BIT)
		RTW_INFO("[%s] Probe Resp  append vendor ie\n", __func__);
	if (vendor_ie_mask & WIFI_ASSOCREQ_VENDOR_IE_BIT)
		RTW_INFO("[%s] Assoc Req append vendor ie\n", __func__);
	if (vendor_ie_mask & WIFI_ASSOCRESP_VENDOR_IE_BIT)
		RTW_INFO("[%s] Assoc Resp append vendor ie\n", __func__);

	pmlmepriv->vendor_ie_mask[0] = vendor_ie_mask;

	return ret;

_clear_path:
	_rtw_memset(pmlmepriv->vendor_ie[0], 0, sizeof(u32) * WLAN_MAX_VENDOR_IE_LEN);
	pmlmepriv->vendor_ielen[0] = 0;
	pmlmepriv->vendor_ie_mask[0] = 0;
	return -EFAULT;
}

int ez_new_sc_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
	_adapter *padapter;
	struct iwreq *wrq = (struct iwreq *)rq;
	u32 buf_len;
	u16 ret;

	if (!dev || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return -EFAULT;
	}

	padapter = (_adapter *)rtw_netdev_priv(dev);

	if (!wrq->u.data.pointer) {
		printk("iwp->pointer == null!!!\n");
		return -EFAULT;
	}

	buf_len = wrq->u.data.length;
	memset(ez_new_sc.buf, 0, EZ_NEW_SC_BUF_LEN);

	if (buf_len > EZ_NEW_SC_BUF_LEN) {
		printk("%s: buf_len Over 512!!!\n", __func__);
		return -EFAULT;
	}

	ret = copy_from_user(ez_new_sc.buf, wrq->u.data.pointer, buf_len);
	if (!ret) {
		int ie_ret;

		ez_new_sc.len = buf_len;
		ie_ret = rtw_ezviz_ie_set(padapter, WIFI_PROBEREQ_VENDOR_IE_BIT,
					  ez_new_sc.buf, (u8)buf_len);
		printk("rtw_vendor_ie_set,ret:%d\n", ie_ret);
		rtw_set_802_11_bssid_list_scan(padapter, NULL);
		smart_flg = 1;
	}

	return ret;
}

int ez_device_info_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
	struct iwreq *wrq = (struct iwreq *)rq;
	u16 len;
	int ret;

	printk("%s()\n", __func__);

	if (!dev || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return 2;
	}

	if (!wrq->u.data.pointer) {
		printk("iwp->pointer == null!!!\n");
		return 1;
	}

	ret = 0;
	len = wrq->u.data.length;
	memset(DeviceInfo, 0, EZ_DEVICE_INFO_LEN);

	if (len <= 8) {
		printk("device sn and model info error!\r\n");
		return ret;
	}

	ret = copy_from_user(DeviceInfo, wrq->u.data.pointer, EZ_DEVICE_SN_LEN);
	if (ret) {
		printk("copey device sn error!\r\n");
		return ret;
	}

	printk("Device SN:%s\r\n", DeviceInfo);

	ret = len - EZ_DEVICE_SN_LEN;
	if (!ret)
		return ret;

	ret = copy_from_user(&DeviceInfo[EZ_DEVICE_SN_LEN],
			     (u8 *)wrq->u.data.pointer + EZ_DEVICE_SN_LEN, ret);
	if (ret)
		printk("copey device model error!\r\n");
	else
		printk("Device Model:%s\r\n", &DeviceInfo[EZ_DEVICE_SN_LEN]);

	return ret;
}

int check_sn_valid(void)
{
	return memcmp(DeviceInfo, null_sn, EZ_DEVICE_SN_LEN) != 0;
}


int check_probe_sync_eid208(u8 *buf, int len)
{
	char sync_code[EZ_SYNC_CODE_LEN + 1] = "EZVIZ";
	int i;

	if (!buf)
		return -1;

	for (i = 0; i < len - 8; i++) {
		if (buf[i] == 208
		    && !memcmp(&buf[i + 2], sync_code, strlen(sync_code))) {
			printk("\n %s: get ez_sync_code \n\r", __func__);
			return i;
		}
	}

	return 0;
}

int ez_probe_response_eid208_handler(u8 *pframe, int len)
{
	u8 *buf;
	int offset;

	if (probe_resp_t.len)
		return 0;

	if (!pframe || len <= 23)
		return -1;

	buf = pframe + 24;
	offset = check_probe_sync_eid208(buf, len - 24);
	if (offset > 0) {
		memcpy(&probe_resp_t, buf + offset, sizeof(probe_resp_t));
		printk("%s()\r\n", __FUNCTION__);
		printk("element:%d\r\n", probe_resp_t.element);
		printk("element len:%d\r\n", probe_resp_t.element_len);
		printk("ID:0x%x\r\n", probe_resp_t.id);
		printk("sync: %c%c%c%c%c\r\n", probe_resp_t.sync[0], probe_resp_t.sync[1],
		       probe_resp_t.sync[2], probe_resp_t.sync[3], probe_resp_t.sync[4]);
		printk("value len:%d,value:%.*s\r\n", probe_resp_t.len, probe_resp_t.len,
		       probe_resp_t.value);
	}

	return offset;
}

int ez_probe_requst_eid208_handler(u8 *pframe, int len)
{
	u8 *buf;
	int offset;

	if (!pframe || len <= 23)
		return -1;

	buf = pframe + 24;
	offset = check_probe_sync_eid208(buf, len - 24);
	if (offset <= 0)
		return offset;

	memcpy(&probe_resp_t, buf + offset, sizeof(probe_resp_t));

	if (memcmp(probe_resp_t.value, DeviceInfo, EZ_DEVICE_SN_LEN))
		return 0;

	if (probe_resp_t.id == 0x6990) {
		probe_resp_t.id = 0x6991;
	} else if (probe_resp_t.id == 0x6992) {
		struct ez_tlv_t tlv;

		if (!err_status)
			return 0;

		probe_resp_t.element_len += 4;
		probe_resp_t.id = 0x6993;
		tlv.id = 0x6994;
		tlv.len = 1;
		tlv.value = err_status;
		memcpy(&probe_resp_t.value[probe_resp_t.len], &tlv, sizeof(tlv));
	}

	printk("%s()\r\n", __FUNCTION__);
	printk("element:%d\r\n", probe_resp_t.element);
	printk("element len:%d\r\n", probe_resp_t.element_len);
	printk("ID:0x%x\r\n", probe_resp_t.id);
	printk("sync: %c%c%c%c%c\r\n", probe_resp_t.sync[0], probe_resp_t.sync[1],
	       probe_resp_t.sync[2], probe_resp_t.sync[3], probe_resp_t.sync[4]);
	printk("value len:%d,value:%.*s\r\n", probe_resp_t.len, probe_resp_t.len,
	       probe_resp_t.value);

	return offset;
}

int ez_probe_req_handler(u8 *pframe, int len)
{
	u8 *buf = pframe + 24;
	int probe_len = len - 24;
	int offset;

	printk("\n  ez_probe_req_handler probe_len=%d! \n", probe_len);

	offset = check_probe_sync_EID(buf, probe_len);
	if (offset > 0) {
		u8 ie_len = buf[offset + 1];

		ez_new_sc.len = ie_len;
		memcpy(ez_new_sc.buf, &buf[offset + 2], ie_len);
		ez_new_sc.done = 1;
		printk("\r\n!!!!!!!!!!GET AP DTAT  SUCCESS!!!!!!!!!!!!!!!!!!\r\n");
	}

	return 0;
}

int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
	_adapter *padapter;
	struct iwreq *wrq = (struct iwreq *)rq;
	struct ez_scan_cmd_t sc;
	int ret;
	u8 len;

	if (!dev || !rq) {
		printk("%s():  net or rq == NULL!\n", __func__);
		return -1;
	}

	padapter = (_adapter *)rtw_netdev_priv(dev);

	if (copy_from_user(&sc, wrq->u.data.pointer, sizeof(sc)))
		return -1;

	switch (sc.cmd) {
	case SCAN_IDLE:
		printk("cmd SCAN_IDLE!\n");
		memset(&probe_req_t, 0, sizeof(probe_req_t));
		memset(&probe_resp_t, 0, sizeof(probe_resp_t));
		ret = 0;
		break;

	case TRIG_SCAN_DEVICE:
		printk("cmd TRIG_SCAN_DEVICE!\n");
		len = sc.len;
		probe_req_t.element = 208;
		probe_req_t.element_len = len + 8;
		probe_req_t.sync[0] = 'E';
		probe_req_t.sync[1] = 'Z';
		probe_req_t.sync[2] = 'V';
		probe_req_t.sync[3] = 'I';
		probe_req_t.sync[4] = 'Z';
		probe_req_t.id = 0x6990;
		goto trig_scan;

	case POLL_DEVICE:
		printk("cmd POLL_DEVICE,sizeof(cmd):%d!\n", sizeof(sc));
		sc.len = probe_resp_t.len;
		memcpy(sc.value, probe_resp_t.value, probe_resp_t.len);
		ret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
		break;

	case TRIG_SCAN_REASON:
		printk("cmd TRIG_SCAN_REASON!\n");
		len = sc.len;
		probe_req_t.element = 208;
		probe_req_t.element_len = len + 8;
		probe_req_t.sync[0] = 'E';
		probe_req_t.sync[1] = 'Z';
		probe_req_t.sync[2] = 'V';
		probe_req_t.sync[3] = 'I';
		probe_req_t.sync[4] = 'Z';
		probe_req_t.id = 0x6992;
trig_scan:
		if (len) {
			probe_req_t.len = len;
			memcpy(probe_req_t.value, sc.value, len);
		}
		if (!probe_req_t.len) {
			ret = 0;
			break;
		}
		printk("element:%d\r\n", 208);
		printk("element len:%d\r\n", probe_req_t.element_len);
		printk("ID:0x%x\r\n", probe_req_t.id);
		printk("sync: %c%c%c%c%c\r\n", probe_req_t.sync[0], probe_req_t.sync[1],
		       probe_req_t.sync[2], probe_req_t.sync[3], probe_req_t.sync[4]);
		printk("value len:%d,value:%s\r\n", probe_req_t.len, probe_req_t.value);
		memset(&probe_resp_t, 0, sizeof(probe_resp_t));
		ret = rtw_ezviz_ie_set(padapter, WIFI_PROBEREQ_VENDOR_IE_BIT,
				       (u8 *)&probe_req_t,
				       (u8)(probe_req_t.element_len + 2));
		printk("rtw_vendor_ie_set,ret:%d!!!\n", ret);
		rtw_set_802_11_bssid_list_scan(padapter, NULL);
		scan_flag = 1;
		break;

	case POLL_REASON: {
		u8 reason[4];

		printk("cmd POLL_REASON!\n");
		memcpy(reason, &probe_resp_t.value[probe_resp_t.len], 4);
		if (*(u16 *)reason == 0x6994) {
			sc.len = reason[2];
			memcpy(sc.value, &reason[3], reason[2]);
			printk("poll reason,len:%d,value:%d\r\n", reason[2], sc.value[0]);
		} else {
			sc.len = 1;
			sc.value[0] = 0xff;
		}
		ret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
		break;
	}

	default:
		ret = -3;
		printk("cmd invalid\n");
		break;
	}

	return ret;
}
