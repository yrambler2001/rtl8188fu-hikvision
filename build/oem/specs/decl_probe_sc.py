# Declaration probes for ez_sc.c:ez_probe_req_handler.
#
# The DECL_UID oracle (build/oem/uidgap.py) says the interval
#
#   ez_device_info_ioctl_handle.__func__ -> check_probe_sync_eid208.__func__
#
# holds 21 declarations here and 16 in the vendor's build.  Moving
# check_sn_valid (which costs exactly 4 and has no __func__ of its own) into
# the preceding interval - which is short by exactly 4 - accounts for all but
# one of those.  This probes which single declaration of ez_probe_req_handler
# the vendor did not have, by removing each in turn and asking whether the
# function stays byte-identical.
UNIT = 'ez_sc'
FUNC = 'ez_probe_req_handler'

AXES = {
    'shape': ['s0', 's1', 's2', 's3', 's4', 's5'],
}

BODY = """int ez_probe_req_handler(u8 *pframe, int len)
{
%(decl)s
\tprintk("\\n  ez_probe_req_handler probe_len=%%d! \\n", %(plen)s);

\t%(off)s = check_probe_sync_EID(%(buf)s, %(plen)s);
\tif (offset > 0) {
%(inner)s\t\tez_new_sc.len = %(ie)s;
\t\tmemcpy(ez_new_sc.buf, &%(buf2)s[offset + 2], %(ie)s);
\t\tez_new_sc.done = 1;
\t\tprintk("\\r\\n!!!!!!!!!!GET AP DTAT  SUCCESS!!!!!!!!!!!!!!!!!!\\r\\n");
\t}

\treturn 0;
}
"""


def render(c):
    s = c['shape']
    decl = ('\tu8 *buf = pframe + 24;\n'
            '\tint probe_len = len - 24;\n'
            '\tint offset;\n')
    plen, buf, buf2, off = 'probe_len', 'buf', 'buf', 'offset'
    inner = '\t\tu8 ie_len = buf[offset + 1];\n\n'
    ie = 'ie_len'
    if s == 's0':                     # baseline
        pass
    elif s == 's1':                   # no ie_len
        inner = ''
        ie = 'buf[offset + 1]'
    elif s == 's2':                   # no ie_len, length read back from ez_new_sc
        inner = ''
        ie = 'buf[offset + 1]'
        return (BODY % {'decl': decl, 'plen': plen, 'buf': buf, 'buf2': buf2,
                        'off': off, 'inner': inner, 'ie': ie}
                ).replace('memcpy(ez_new_sc.buf, &buf[offset + 2], buf[offset + 1]);',
                          'memcpy(ez_new_sc.buf, &buf[offset + 2], ez_new_sc.len);')
    elif s == 's3':                   # no probe_len
        decl = ('\tu8 *buf = pframe + 24;\n'
                '\tint offset;\n')
        plen = 'len - 24'
    elif s == 's4':                   # no buf
        decl = ('\tint probe_len = len - 24;\n'
                '\tint offset;\n')
        buf = buf2 = 'pframe + 24'
        inner = '\t\tu8 ie_len = pframe[offset + 26];\n\n'
    else:                             # s5: offset declared with its initialiser
        decl = ('\tu8 *buf = pframe + 24;\n'
                '\tint probe_len = len - 24;\n')
        off = 'int offset'
    return BODY % {'decl': decl, 'plen': plen, 'buf': buf, 'buf2': buf2,
                   'off': off, 'inner': inner, 'ie': ie}
