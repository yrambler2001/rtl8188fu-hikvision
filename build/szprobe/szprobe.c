/* Driver-side struct-size oracle.
 *
 * Compiled with the *driver's own* include path and EXTRA_CFLAGS (lifted
 * verbatim from core/.rtw_mlme.o.cmd), so every sizeof() below is the size the
 * real build would use. Read the answers back with:
 *     arm-linux-gnueabi-readelf -sW szprobe.o | grep szp_
 * Takes ~1 s, so whole #ifdef sweeps are cheap.
 */
#include <drv_types.h>

#define SZ(name, expr) char szp_##name[expr];
#define OF(name, t, m) char szo_##name[offsetof(t, m) + 1];

SZ(mlme_priv,            sizeof(struct mlme_priv))
SZ(align_mlme_priv,      __alignof__(struct mlme_priv))
SZ(mlme_ext_priv,        sizeof(struct mlme_ext_priv))
SZ(ADAPTER,              sizeof(_adapter))
SZ(dvobj_priv,           sizeof(struct dvobj_priv))
SZ(wlan_network,         sizeof(struct wlan_network))
SZ(WLAN_BSSID_EX,        sizeof(WLAN_BSSID_EX))
SZ(ht_priv,              sizeof(struct ht_priv))
SZ(qos_priv,             sizeof(struct qos_priv))
SZ(beacon_keys,          sizeof(struct beacon_keys))
SZ(RT_LINK_DETECT_T,     sizeof(RT_LINK_DETECT_T))
SZ(NDIS_802_11_SSID,     sizeof(NDIS_802_11_SSID))
SZ(_queue,               sizeof(_queue))
SZ(_lock,                sizeof(_lock))
SZ(_timer,               sizeof(_timer))
SZ(ATOMIC_T,             sizeof(ATOMIC_T))
SZ(systime,              sizeof(systime))
#ifdef CONFIG_RTW_80211R
SZ(ft_roam_info,         sizeof(struct ft_roam_info))
#endif
#if defined(CONFIG_RTW_WNM) || defined(CONFIG_RTW_80211K)
SZ(roam_nb_info,         sizeof(struct roam_nb_info))
#endif
#ifdef CONFIG_RTW_MBO
SZ(mbo_attr_info,        sizeof(struct mbo_attr_info))
#endif
#ifdef CONFIG_80211AC_VHT
SZ(vht_priv,             sizeof(struct vht_priv))
#endif
#ifdef CONFIG_APPEND_VENDOR_IE_ENABLE
SZ(vendor_ie_block,      WLAN_MAX_VENDOR_IE_NUM * (8 + WLAN_MAX_VENDOR_IE_LEN))
#endif

OF(A_dvobj,              _adapter, dvobj)
OF(A_mlmepriv,           _adapter, mlmepriv)
OF(A_mlmeextpriv,        _adapter, mlmeextpriv)
OF(A_cmdpriv,            _adapter, cmdpriv)
OF(A_evtpriv,            _adapter, evtpriv)
OF(A_iopriv,             _adapter, iopriv)
OF(A_registrypriv,       _adapter, registrypriv)
OF(A_HalData,            _adapter, HalData)
OF(A_xmitpriv,           _adapter, xmitpriv)
OF(A_recvpriv,           _adapter, recvpriv)
OF(A_stapriv,            _adapter, stapriv)
OF(A_securitypriv,       _adapter, securitypriv)

OF(M_cur_network,        struct mlme_priv, cur_network)
OF(M_qospriv,            struct mlme_priv, qospriv)
OF(M_LinkDetectInfo,     struct mlme_priv, LinkDetectInfo)
OF(M_assoc_req,          struct mlme_priv, assoc_req)
OF(M_acm_mask,           struct mlme_priv, acm_mask)
OF(M_cur_beacon_keys,    struct mlme_priv, cur_beacon_keys)
OF(M_assoc_ssid,         struct mlme_priv, assoc_ssid)
OF(M_free_bss_pool,      struct mlme_priv, free_bss_pool)
OF(M_mbo_attr,           struct mlme_priv, mbo_attr)
#ifdef CONFIG_APPEND_VENDOR_IE_ENABLE
OF(M_vendor_ie_mask,     struct mlme_priv, vendor_ie_mask)
OF(M_vendor_ie,          struct mlme_priv, vendor_ie)
OF(M_vendor_ielen,       struct mlme_priv, vendor_ielen)
#endif
OF(M_lastscantime,       struct mlme_priv, lastscantime)
