# Variant spec for ez_sc.c:ez_scan_device_ioctl_handle - stage 2.
#
# This is the most expensive residual in the whole file.  The function is four
# bytes long because its literal pool has one word ours needs and the shipped
# build does not: `.LANCHOR0+622`, the address of `probe_req_t.value`.  That
# word sits in the middle of the pool, so every pool entry after it moves by
# four, and 17 of the 18 unmatched entries in `.rel.text` - 280 of the 348
# bytes still differing in the whole module - are that shift.
#
# The shipped build never needs the constant.  It materialises the OEM .bss
# anchor once (`ldr r4, .LANCHOR0`), derives `&probe_req_t` from it with
# `add r5, r4, #612` - 612 is an encodable ARM immediate, 622 is not - and
# then writes `&probe_req_t.value` as `add r0, r5, #10`.  Ours only ever has
# the bare anchor in a register at that point, so it loads the whole symbolic
# constant from the pool.
#
# Whether GCC splits `anchor + 622` into two adds or loads it whole is a CSE
# cost decision, and it comes out the shipped way only if `anchor + 612`
# already has a register.  These axes vary the ways the source can ask for
# that: through a struct pointer, a byte pointer with explicit offsets, a
# pointer to the value array, and the order of the writes around it.
UNIT = 'ez_sc'
FUNC = 'ez_scan_device_ioctl_handle'

AXES = {
    'base': ['b0', 'b1', 'b2', 'b3', 'b4', 'b5'],
    'copy': ['c0', 'c1', 'c2'],
    'idw': ['i0', 'i1', 'i2'],
    'lentype': ['u8', 'int', 'u32'],
    'declpos': ['p0', 'p1'],
}

HEAD = ('int ez_scan_device_ioctl_handle(struct net_device *dev, struct ifreq *rq, int cmd)\n'
        '{\n')

TAIL = """
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


def render(c):
    base, copy, idw, lentype, declpos = (c['base'], c['copy'], c['idw'],
                                         c['lentype'], c['declpos'])
    # how probe_req_t is written
    if base == 'b0':                      # by name
        decl, R, RA, V = '', 'probe_req_t.', '&probe_req_t', 'probe_req_t.value'
    elif base == 'b1':                    # struct pointer
        decl = '\tstruct ez_probe_t *req = &probe_req_t;\n'
        R, RA, V = 'req->', 'req', 'req->value'
    elif base == 'b2':                    # struct pointer + value pointer
        decl = ('\tstruct ez_probe_t *req = &probe_req_t;\n'
                '\tu8 *rv = probe_req_t.value;\n')
        R, RA, V = 'req->', 'req', 'rv'
    elif base == 'b3':                    # byte pointer with explicit offsets
        decl = '\tu8 *rb = (u8 *)&probe_req_t;\n'
        R, RA, V = None, 'rb', 'rb + 10'
    elif base == 'b4':                    # value pointer only
        decl = '\tu8 *rv = probe_req_t.value;\n'
        R, RA, V = 'probe_req_t.', '&probe_req_t', 'rv'
    else:                                 # b5: pointer assigned in the case arm
        decl = '\tstruct ez_probe_t *req;\n'
        R, RA, V = 'req->', 'req', 'req->value'

    def fill(idval):
        if base == 'b3':
            s = ('\t\trb[0] = 208;\n'
                 '\t\trb[1] = len + 8;\n'
                 "\t\trb[2] = 'E';\n\t\trb[3] = 'Z';\n\t\trb[4] = 'V';\n"
                 "\t\trb[5] = 'I';\n\t\trb[6] = 'Z';\n")
            if idw == 'i0':
                s += '\t\t*(u16 *)(rb + 7) = %s;\n' % idval
            elif idw == 'i1':
                s += ('\t\trb[7] = %s & 0xff;\n\t\trb[8] = %s >> 8;\n'
                      % (idval, idval))
            else:
                s += '\t\tprobe_req_t.id = %s;\n' % idval
            return s
        pre = '\t\treq = &probe_req_t;\n' if base == 'b5' else ''
        s = (pre +
             '\t\t%selement = 208;\n' % R +
             '\t\t%selement_len = len + 8;\n' % R +
             "\t\t%ssync[0] = 'E';\n" % R +
             "\t\t%ssync[1] = 'Z';\n" % R +
             "\t\t%ssync[2] = 'V';\n" % R +
             "\t\t%ssync[3] = 'I';\n" % R +
             "\t\t%ssync[4] = 'Z';\n" % R)
        if idw == 'i0':
            s += '\t\t%sid = %s;\n' % (R, idval)
        elif idw == 'i1':
            s += ('\t\t%ssync[5] = %s & 0xff;\n' % (R, idval) if False else
                  '\t\t%sid = (u16)%s;\n' % (R, idval))
        else:
            s += '\t\tprobe_req_t.id = %s;\n' % idval
        return s

    LEN = '%slen' % (R if R else 'probe_req_t.')
    if base == 'b3':
        LEN = 'rb[9]'
    ELEN = '%selement_len' % (R if R else 'probe_req_t.')
    if base == 'b3':
        ELEN = 'rb[1]'
    ID = '%sid' % (R if R else 'probe_req_t.')
    if base == 'b3':
        ID = '*(u16 *)(rb + 7)'
    SYNC = [('%ssync[%d]' % (R, k)) if base != 'b3' else 'rb[%d]' % (2 + k)
            for k in range(5)]

    if copy == 'c0':
        body_copy = ('\t\tif (len) {\n\t\t\t%s = len;\n'
                     '\t\t\tmemcpy(%s, sc.value, len);\n\t\t}\n' % (LEN, V))
    elif copy == 'c1':
        body_copy = ('\t\tif (len) {\n\t\t\tmemcpy(%s, sc.value, len);\n'
                     '\t\t\t%s = len;\n\t\t}\n' % (V, LEN))
    else:
        body_copy = ('\t\tif (len != 0) {\n\t\t\t%s = len;\n'
                     '\t\t\tmemcpy(&%s[0], sc.value, len);\n\t\t}\n'
                     % (LEN, V if base != 'b3' else '*(rb + 10)'))
        if base == 'b3':
            body_copy = ('\t\tif (len != 0) {\n\t\t\t%s = len;\n'
                         '\t\t\tmemcpy(rb + 10, sc.value, len);\n\t\t}\n' % LEN)

    decls = ['\t_adapter *padapter;\n',
             '\tstruct iwreq *wrq = (struct iwreq *)rq;\n',
             '\tstruct ez_scan_cmd_t sc;\n',
             '\tint ret;\n',
             '\t%s len;\n' % lentype]
    if declpos == 'p0':
        decls.append(decl)
    else:
        decls.insert(1, decl)

    return (HEAD + ''.join(decls) + """
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
\t\tmemset(""" + RA + """, 0, sizeof(probe_req_t));
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
""" + body_copy + """\t\tif (!""" + LEN + """) {
\t\t\tret = 0;
\t\t\tbreak;
\t\t}
\t\tprintk("element:%d\\r\\n", 208);
\t\tprintk("element len:%d\\r\\n", """ + ELEN + """);
\t\tprintk("ID:0x%x\\r\\n", """ + ID + """);
\t\tprintk("sync: %c%c%c%c%c\\r\\n", """ + SYNC[0] + ', ' + SYNC[1] + """,
\t\t       """ + SYNC[2] + ', ' + SYNC[3] + ', ' + SYNC[4] + """);
\t\tprintk("value len:%d,value:%s\\r\\n", """ + LEN + ', ' + V + """);
\t\tmemset(&probe_resp_t, 0, sizeof(probe_resp_t));
\t\tret = rtw_ezviz_ie_set(padapter, WIFI_PROBEREQ_VENDOR_IE_BIT,
\t\t\t\t       (u8 *)""" + RA + """,
\t\t\t\t       (u8)(""" + ELEN + """ + 2));
\t\tprintk("rtw_vendor_ie_set,ret:%d!!!\\n", ret);
\t\trtw_set_802_11_bssid_list_scan(padapter, NULL);
\t\tscan_flag = 1;
\t\tbreak;
""" + TAIL)
