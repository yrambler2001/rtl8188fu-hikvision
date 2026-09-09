# Variant spec for ez_sc.c:ez_scan_device_ioctl_handle.
#
# +4 bytes: one extra literal-pool word.  Both builds put the OEM .bss anchor
# (.LANCHOR0, at err_status) and .LANCHOR0+612 (probe_req_t) and
# .LANCHOR0+570 (probe_resp_t) in the pool.  The shipped build additionally
# derives &probe_req_t as `add r5, r4, #612` from the anchor register early in
# the TRIG_SCAN_DEVICE block, so `&probe_req_t.value` is `add r0, r5, #10`.
# Ours only ever has the bare anchor in a register there, and 622 is not an
# encodable ARM immediate, so it needs a fourth pool word, .LANCHOR0+622.
#
# Sweep the ways the OEM .bss objects can be reached: through a cached local
# pointer, through the struct name, through a pointer to the value array, and
# the order in which the fields are written.
UNIT = 'ez_sc'
FUNC = 'ez_scan_device_ioctl_handle'

AXES = {
    'ptr': ['q0', 'q1', 'q2', 'q3', 'q4', 'q5'],
    'resp': ['r0', 'r1', 'r2'],
    'val': ['v0', 'v1', 'v2'],
    'lentype': ['u8', 'int', 'u32', 'char', 's8'],
    'order': ['o0', 'o1'],
}

HEAD = ('int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)\n'
        '{\n')


def render(c):
    ptr, resp, val, lentype, order = (c['ptr'], c['resp'], c['val'],
                                      c['lentype'], c['order'])
    # how probe_req_t is named
    REQ = {'q0': 'probe_req_t.', 'q1': 'req->', 'q2': 'req->',
           'q3': 'probe_req_t.', 'q4': 'req->', 'q5': 'req->'}[ptr]
    REQA = {'q0': '&probe_req_t', 'q1': 'req', 'q2': 'req',
            'q3': '&probe_req_t', 'q4': 'req', 'q5': 'req'}[ptr]
    RESP = {'r0': 'probe_resp_t.', 'r1': 'resp->', 'r2': 'probe_resp_t.'}[resp]
    RESPA = {'r0': '&probe_resp_t', 'r1': 'resp', 'r2': '&probe_resp_t'}[resp]

    decl = ['\t_adapter *padapter;\n',
            '\tstruct iwreq *wrq = (struct iwreq *)rq;\n',
            '\tstruct ez_scan_cmd_t sc;\n',
            '\tint ret;\n',
            '\t%s len;\n' % lentype]
    if ptr in ('q1', 'q4'):
        decl.insert(1, '\tstruct ez_probe_t *req = &probe_req_t;\n')
    elif ptr in ('q2', 'q5'):
        decl.append('\tstruct ez_probe_t *req = &probe_req_t;\n')
    if resp == 'r1':
        decl.append('\tstruct ez_probe_t *resp = &probe_resp_t;\n')
    if ptr in ('q3', 'q4', 'q5'):
        decl.append('\tu8 *rv = %svalue;\n' % REQ if ptr != 'q3'
                    else '\tu8 *rv = probe_req_t.value;\n')
    VAL = {'v0': REQ + 'value', 'v1': '&%svalue[0]' % REQ, 'v2': REQ + 'value'}[val]
    if ptr in ('q3', 'q4', 'q5'):
        VAL = 'rv'

    fill = (
        "\t\t%(R)selement = 208;\n"
        "\t\t%(R)selement_len = len + 8;\n"
        "\t\t%(R)ssync[0] = 'E';\n"
        "\t\t%(R)ssync[1] = 'Z';\n"
        "\t\t%(R)ssync[2] = 'V';\n"
        "\t\t%(R)ssync[3] = 'I';\n"
        "\t\t%(R)ssync[4] = 'Z';\n") % {'R': REQ}

    s = HEAD + ''.join(decl) + """
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
\t\tmemset(@REQA@, 0, sizeof(probe_req_t));
\t\tmemset(@RESPA@, 0, sizeof(probe_resp_t));
\t\tret = 0;
\t\tbreak;

\tcase TRIG_SCAN_DEVICE:
\t\tprintk("cmd TRIG_SCAN_DEVICE!\\n");
\t\tlen = sc.len;
FILL\t\t@REQ@id = 0x6990;
\t\tgoto trig_scan;

\tcase POLL_DEVICE:
\t\tprintk("cmd POLL_DEVICE,sizeof(cmd):%d!\\n", sizeof(sc));
\t\tsc.len = @RESP@len;
\t\tmemcpy(sc.value, @RESP@value, @RESP@len);
\t\tret = copy_to_user(wrq->u.data.pointer, &sc, sizeof(sc));
\t\tbreak;

\tcase TRIG_SCAN_REASON:
\t\tprintk("cmd TRIG_SCAN_REASON!\\n");
\t\tlen = sc.len;
FILL\t\t@REQ@id = 0x6992;
trig_scan:
\t\tif (len) {
\t\t\t@REQ@len = len;
\t\t\tmemcpy(@VAL@, sc.value, len);
\t\t}
\t\tif (!@REQ@len) {
\t\t\tret = 0;
\t\t\tbreak;
\t\t}
\t\tprintk("element:%d\\r\\n", 208);
\t\tprintk("element len:%d\\r\\n", @REQ@element_len);
\t\tprintk("ID:0x%x\\r\\n", @REQ@id);
\t\tprintk("sync: %c%c%c%c%c\\r\\n", @REQ@sync[0], @REQ@sync[1],
\t\t       @REQ@sync[2], @REQ@sync[3], @REQ@sync[4]);
\t\tprintk("value len:%d,value:%s\\r\\n", @REQ@len, @VAL@);
\t\tmemset(@RESPA@, 0, sizeof(probe_resp_t));
\t\tret = rtw_ezviz_ie_set(padapter, WIFI_PROBEREQ_VENDOR_IE_BIT,
\t\t\t\t       (u8 *)@REQA@,
\t\t\t\t       (u8)(@REQ@element_len + 2));
\t\tprintk("rtw_vendor_ie_set,ret:%d!!!\\n", ret);
\t\trtw_set_802_11_bssid_list_scan(padapter, NULL);
\t\tscan_flag = 1;
\t\tbreak;

\tcase POLL_REASON: {
\t\tu8 reason[4];

\t\tprintk("cmd POLL_REASON!\\n");
\t\tmemcpy(reason, &@RESP@value[@RESP@len], 4);
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
    s = s.replace('FILL', fill).replace('@REQA@', REQA).replace('@RESPA@', RESPA)
    s = s.replace('@REQ@', REQ).replace('@RESP@', RESP).replace('@VAL@', VAL)
    if order == 'o1':
        # write element_len last instead of second
        s = s.replace("%selement_len = len + 8;\n" % REQ, '')
        s = s.replace("%sid = 0x6990;\n" % REQ,
                      "%selement_len = len + 8;\n\t\t%sid = 0x6990;\n" % (REQ, REQ))
        s = s.replace("%sid = 0x6992;\n" % REQ,
                      "%selement_len = len + 8;\n\t\t%sid = 0x6992;\n" % (REQ, REQ))
    return s
