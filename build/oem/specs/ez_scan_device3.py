# Variant spec for ez_sc.c:ez_scan_device_ioctl_handle - stage 3, the fill order.
#
# The RTL dumps say exactly where the extra pool word comes from.  At expand
# both the `probe_req_t.id` store and the memcpy destination build
# `&probe_req_t` explicitly:
#
#	r276 = .LANCHOR0
#	r277 = r276 + 612	<- &probe_req_t
#	r278 = r277 + 10	<- &probe_req_t.value
#
# and the shipped build keeps that (`add r5, r4, #612` in both TRIG arms,
# then `add r0, r5, #10`).  Here the two never get combined - the `id` store's
# copy lives in the TRIG arm and the memcpy's in the `if (len)` block - so by
# `cse_local` the second is folded to the single constant `.LANCHOR0+622`,
# which has to go in the pool.  That one word displaces every pool entry after
# it, and those relocations are 280 of the 348 bytes still differing.
#
# So this varies the order of the eight field writes - which decides where in
# the block `&probe_req_t` is first built - and how `id` is spelt.
import itertools

UNIT = 'ez_sc'
FUNC = 'ez_scan_device_ioctl_handle'

FIELDS = [
    ('el', '\t\tprobe_req_t.element = 208;\n'),
    ('ln', '\t\tprobe_req_t.element_len = len + 8;\n'),
    ('s0', "\t\tprobe_req_t.sync[0] = 'E';\n"),
    ('s1', "\t\tprobe_req_t.sync[1] = 'Z';\n"),
    ('s2', "\t\tprobe_req_t.sync[2] = 'V';\n"),
    ('s3', "\t\tprobe_req_t.sync[3] = 'I';\n"),
    ('s4', "\t\tprobe_req_t.sync[4] = 'Z';\n"),
]

# A sample of orders: the identity, every rotation, every single-element move
# of the id store, and a few groupings.  The full 8! is not worth the compile
# time when every axis tried so far has been neutral.
ORDERS = []
base = list(range(7))
ORDERS.append(('o00', base, 7))                    # id last (current)
for k in range(8):
    ORDERS.append(('i%02d' % k, base, k))          # id at every position
for r in range(1, 7):
    ORDERS.append(('r%02d' % r, base[r:] + base[:r], 7))
for a, b in itertools.combinations(range(7), 2):
    o = list(base)
    o[a], o[b] = o[b], o[a]
    ORDERS.append(('s%d%d' % (a, b), o, 7))

AXES = {
    'order': [(t, (o, k)) for t, o, k in ORDERS],
    'idw': ['w0', 'w1', 'w2'],
}

ID = {
    'w0': '\t\tprobe_req_t.id = %s;\n',
    'w1': '\t\tprobe_req_t.id = (u16)%s;\n',
    'w2': '\t\t*(u16 *)&probe_req_t.id = %s;\n',
}


def render(c):
    order, idpos = c['order']
    idw = c['idw']

    def fill(idval):
        parts = [FIELDS[i][1] for i in order]
        parts.insert(idpos, ID[idw] % idval)
        return ''.join(parts)

    return ("""int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)
{
\t_adapter *padapter;
\tstruct iwreq *wrq = (struct iwreq *)rq;
\tstruct ez_scan_cmd_t sc;
\tint ret;
\tu8 len;

\tif (!dev || !rq) {
\t\tprintk("%s():  net or rq == NULL!\\n", __func__);
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

\tcase TRIG_SCAN_DEVICE:
\t\tprintk("cmd TRIG_SCAN_DEVICE!\\n");
\t\tlen = sc.len;
""" + fill('0x6990') + """\t\tgoto trig_scan;

\tcase POLL_DEVICE:
\t\tprintk("cmd POLL_DEVICE,sizeof(cmd):%d!\\n", sizeof(sc));
\t\tsc.len = probe_resp_t.len;
\t\tmemcpy(sc.value, probe_resp_t.value, probe_resp_t.len);
\t\tret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
\t\tbreak;

\tcase TRIG_SCAN_REASON:
\t\tprintk("cmd TRIG_SCAN_REASON!\\n");
\t\tlen = sc.len;
""" + fill('0x6992') + """trig_scan:
\t\tif (len) {
\t\t\tprobe_req_t.len = len;
\t\t\tmemcpy(probe_req_t.value, sc.value, len);
\t\t}
\t\tif (!probe_req_t.len) {
\t\t\tret = 0;
\t\t\tbreak;
\t\t}
\t\tprintk("element:%d\\r\\n", 208);
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
""")
