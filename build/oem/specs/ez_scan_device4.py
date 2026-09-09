# Variant spec for ez_sc.c:ez_scan_device_ioctl_handle - stage 4, where the
# shared tail starts.
#
# Section 16 traced the extra pool word to `cse_local`: `&probe_req_t` is built
# twice - once for the unaligned `probe_req_t.id` store in each TRIG arm, once
# for the memcpy destination in the `if (len)` block after the merge - the two
# copies live in different basic blocks, no global pass combines them, and the
# second is folded into the single constant `.LANCHOR0+622`.
#
# The fix that worked for ez_strsep (section 18) was to *duplicate* a block in
# the source and let cross-jumping merge it back: same final layout, different
# expression graph on the way there.  Here that means moving the `if (len)`
# block - and progressively more of the shared tail - up into both TRIG arms,
# so the memcpy's `&probe_req_t` is in the same block as the `id` store's.
UNIT = 'ez_sc'
FUNC = 'ez_scan_device_ioctl_handle'

AXES = {
    'split': ['k0', 'k1', 'k2', 'k3'],
    'lentype': ['u8', 'int', 'u32'],
}

HEAD = """int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
\t_adapter *padapter;
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tstruct ez_scan_cmd_t sc;
\tint ret;
\t%s len;

\tif (!dev || !rq) {
\t\tprintk("%%s():  net or rq == NULL!\\n", __func__);
\t\treturn -1;
\t}

\tpadapter = (_adapter *)rtw_netdev_priv(dev);

\tif (copy_from_user(&sc, wrq->u.data.pointer, sizeof(sc)))
\t\treturn -1;

\tswitch (sc.cmd) {
\tcase SCAN_IDLE:
\t\tprintk("cmd SCAN_IDLE!\\n");
\t\tmemset(&probe_req_t, 0, sizeof(probe_req_t));
\t\tmemset(&probe_resp_t, 0, sizeof(probe_resp_t));
\t\tret = 0;
\t\tbreak;
"""

FILL = """\t\tlen = sc.len;
\t\tprobe_req_t.element = 208;
\t\tprobe_req_t.element_len = len + 8;
\t\tprobe_req_t.sync[0] = 'E';
\t\tprobe_req_t.sync[1] = 'Z';
\t\tprobe_req_t.sync[2] = 'V';
\t\tprobe_req_t.sync[3] = 'I';
\t\tprobe_req_t.sync[4] = 'Z';
\t\tprobe_req_t.id = %s;
"""

COPY = """\t\tif (len) {
\t\t\tprobe_req_t.len = len;
\t\t\tmemcpy(probe_req_t.value, sc.value, len);
\t\t}
"""

ZERO = """\t\tif (!probe_req_t.len) {
\t\t\tret = 0;
\t\t\tbreak;
\t\t}
"""

TAIL_SHARED = """\t\tprintk("element:%d\\r\\n", 208);
\t\tprintk("element len:%d\\r\\n", probe_req_t.element_len);
\t\tprintk("ID:0x%x\\r\\n", probe_req_t.id);
\t\tprintk("sync: %c%c%c%c%c\\r\\n", probe_req_t.sync[0], probe_req_t.sync[1],
\t\t       probe_req_t.sync[2], probe_req_t.sync[3], probe_req_t.sync[4]);
\t\tprintk("value len:%d,value:%s\\r\\n", probe_req_t.len, probe_req_t.value);
\t\tmemset(&probe_resp_t, 0, sizeof(probe_resp_t));
\t\tret = rtw_ezviz_ie_set(padapter, WIFI_PROBEREQ_VENDOR_IE_BIT,
\t\t\t\t       (u8 *)&probe_req_t,
\t\t\t\t       (u8)(probe_req_t.element_len + 2));
\t\tprintk("rtw_vendor_ie_set,ret:%d!!!\\n", ret);
\t\trtw_set_802_11_bssid_list_scan(padapter, NULL);
\t\tscan_flag = 1;
\t\tbreak;
"""

REST = """
\tcase POLL_REASON: {
\t\tu8 reason[4];

\t\tprintk("cmd POLL_REASON!\\n");
\t\tmemcpy(reason, &probe_resp_t.value[probe_resp_t.len], 4);
\t\tif (*(u16 *)reason == 0x6994) {
\t\t\tsc.len = reason[2];
\t\t\tmemcpy(sc.value, &reason[3], reason[2]);
\t\t\tprintk("poll reason,len:%d,value:%d\\r\\n", reason[2], sc.value[0]);
\t\t} else {
\t\t\tsc.len = 1;
\t\t\tsc.value[0] = 0xff;
\t\t}
\t\tret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
\t\tbreak;
\t}

\tdefault:
\t\tret = -3;
\t\tprintk("cmd invalid\\n");
\t\tbreak;
\t}

\treturn ret;
}
"""

POLL = """
\tcase POLL_DEVICE:
\t\tprintk("cmd POLL_DEVICE,sizeof(cmd):%d!\\n", sizeof(sc));
\t\tsc.len = probe_resp_t.len;
\t\tmemcpy(sc.value, probe_resp_t.value, probe_resp_t.len);
\t\tret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
\t\tbreak;
"""


def render(c):
    k = c['split']
    dup = {'k0': '', 'k1': COPY, 'k2': COPY + ZERO,
           'k3': COPY + ZERO + TAIL_SHARED}[k]
    shared = {'k0': COPY + ZERO + TAIL_SHARED,
              'k1': ZERO + TAIL_SHARED,
              'k2': TAIL_SHARED,
              'k3': ''}[k]
    s = HEAD % c['lentype']
    s += ('\n\tcase TRIG_SCAN_DEVICE:\n'
          '\t\tprintk("cmd TRIG_SCAN_DEVICE!\\n");\n' + FILL % '0x6990' + dup)
    if k == 'k3':
        s += POLL
        s += ('\n\tcase TRIG_SCAN_REASON:\n'
              '\t\tprintk("cmd TRIG_SCAN_REASON!\\n");\n'
              + FILL % '0x6992' + dup)
    else:
        s += '\t\tgoto trig_scan;\n'
        s += POLL
        s += ('\n\tcase TRIG_SCAN_REASON:\n'
              '\t\tprintk("cmd TRIG_SCAN_REASON!\\n");\n'
              + FILL % '0x6992' + dup + 'trig_scan:\n' + shared)
    return s + REST
