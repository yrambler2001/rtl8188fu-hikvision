# Declaration probes for ez_wifi_config.c.
#
# The DECL_UID oracle (build/oem/uidgap.py) says two intervals of this file
# hold one declaration *more* than the vendor's:
#
#   ez_set_country.__func__     -> ez_wifi_preinit.__func__          16 vs 17
#   ez_wifi_preinit.__FUNCTION__-> ez_read_rssi_per_ant_ioctl.__func__ 18 vs 19
#
# Every function in both intervals is already byte-identical, so whichever
# declaration is one too many must be one that emits no code of its own - a
# cached pointer that folds into the address arithmetic, or a label.  This
# spec removes each candidate in turn and asks whether the function stays
# byte-identical; one that does is a real reduction, not a guess.
#
#   gen.py --spec build/oem/specs/decl_probe_wc.py --out build/oem/lab/dpw
#   lab.py --unit ez_wifi_config --dir build/oem/lab/dpw --fn ez_read_rssi_per_ant_ioctl
UNIT = 'ez_wifi_config'
FUNC = 'ez_read_rssi_per_ant_ioctl'

AXES = {
    'shape': ['s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7'],
}

HEAD = ('int ez_read_rssi_per_ant_ioctl(struct net_device *dev, struct ifreq *rq, int cmd)\n'
        '{\n')

BODY = """
\tprintk("\\n ####### ez_read_rssi_per_ant_ioctl ENTER  , cmd = %%x\\n", cmd);

\tif (dev && rq) {
\t\tif (%(ptr)s)
\t\t\tgoto do_read;
\t} else {
\t\tprintk("%%s():  net or rq == NULL!\\n", __func__);
\t\treturn -1;
\t}

\tprintk("iwp == NULL or iwp->pointer == null!!!\\n");
\treturn -1;

do_read:
%(setup)s
\tmemset(&rssi, 0, sizeof(rssi));

\tprintk("RxRate = %%s, RSSI_A = %%d(%%%%), RSSI_B = %%d(%%%%)\\n",
\t       HDATA_RATE(%(odm)srx_rate), %(odm)srssi_a, %(odm)srssi_b);

\trssi.Valid = 1;
\trssi.Rssi_AVG = %(rssi_avg)s;
\trssi.Rssi_ANT0 = %(odm)srssi_a - 100;
\trssi.Rssi_ANT1 = %(odm)srssi_a - 100;

\tprintk("rssi.Valid = %%d, RxRate = %%s, Rssi_ANT0 = %%d(%%%%), Rssi_ANT1 = %%d(%%%%), rssi.Rssi_AVG = %%d\\n",
\t       rssi.Valid, HDATA_RATE(%(odm)srx_rate), rssi.Rssi_ANT0, rssi.Rssi_ANT1,
\t       rssi.Rssi_AVG);

\treturn copy_to_user(%(ptr)s, &rssi, sizeof(rssi));
}
"""

FULL_DECL = ('\t_adapter *padapter;\n'
             '\tstruct iwreq *wrq = (struct iwreq *)rq;\n'
             '\tHAL_DATA_TYPE *pHalData;\n'
             '\tstruct dm_struct *pDM_Odm;\n'
             '\tstruct recv_priv *precvpriv;\n'
             '\tstruct ez_rssi_per_ant rssi;\n')
FULL_SETUP = ('\tpadapter = (_adapter *)rtw_netdev_priv(dev);\n'
              '\tprecvpriv = &padapter->recvpriv;\n'
              '\tpHalData = GET_HAL_DATA(padapter);\n'
              '\tpDM_Odm = &pHalData->odmpriv;\n')


def render(c):
    s = c['shape']
    decl, setup = FULL_DECL, FULL_SETUP
    ptr = 'wrq->u.data.pointer'
    odm = 'pDM_Odm->'
    avg = 'precvpriv->rssi'
    if s == 's0':                       # baseline
        pass
    elif s == 's1':                     # no precvpriv
        decl = decl.replace('\tstruct recv_priv *precvpriv;\n', '')
        setup = setup.replace('\tprecvpriv = &padapter->recvpriv;\n', '')
        avg = 'padapter->recvpriv.rssi'
    elif s == 's2':                     # no pHalData
        decl = decl.replace('\tHAL_DATA_TYPE *pHalData;\n', '')
        setup = setup.replace('\tpHalData = GET_HAL_DATA(padapter);\n', '')
        setup = setup.replace('\tpDM_Odm = &pHalData->odmpriv;\n',
                              '\tpDM_Odm = &GET_HAL_DATA(padapter)->odmpriv;\n')
    elif s == 's3':                     # no pDM_Odm
        decl = decl.replace('\tstruct dm_struct *pDM_Odm;\n', '')
        setup = setup.replace('\tpDM_Odm = &pHalData->odmpriv;\n', '')
        odm = 'pHalData->odmpriv.'
    elif s == 's4':                     # no wrq
        decl = decl.replace('\tstruct iwreq *wrq = (struct iwreq *)rq;\n', '')
        ptr = '((struct iwreq *)rq)->u.data.pointer'
    elif s == 's5':                     # neither precvpriv nor pHalData
        decl = decl.replace('\tstruct recv_priv *precvpriv;\n', '')
        decl = decl.replace('\tHAL_DATA_TYPE *pHalData;\n', '')
        setup = setup.replace('\tprecvpriv = &padapter->recvpriv;\n', '')
        setup = setup.replace('\tpHalData = GET_HAL_DATA(padapter);\n', '')
        setup = setup.replace('\tpDM_Odm = &pHalData->odmpriv;\n',
                              '\tpDM_Odm = &GET_HAL_DATA(padapter)->odmpriv;\n')
        avg = 'padapter->recvpriv.rssi'
    elif s == 's6':                     # padapter initialised in its declaration
        decl = decl.replace('\t_adapter *padapter;\n', '')
        setup = setup.replace('\tpadapter = (_adapter *)rtw_netdev_priv(dev);\n',
                              '\t_adapter *padapter = (_adapter *)rtw_netdev_priv(dev);\n')
    else:                               # s7: no precvpriv, no pDM_Odm
        decl = decl.replace('\tstruct recv_priv *precvpriv;\n', '')
        decl = decl.replace('\tstruct dm_struct *pDM_Odm;\n', '')
        setup = setup.replace('\tprecvpriv = &padapter->recvpriv;\n', '')
        setup = setup.replace('\tpDM_Odm = &pHalData->odmpriv;\n', '')
        odm = 'pHalData->odmpriv.'
        avg = 'padapter->recvpriv.rssi'
    return HEAD + decl + (BODY % {'ptr': ptr, 'setup': setup,
                                  'odm': odm, 'rssi_avg': avg})
