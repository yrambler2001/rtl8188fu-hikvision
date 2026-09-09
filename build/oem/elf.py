import struct, sys

class ELF:
    def __init__(self, path):
        self.d = open(path,'rb').read()
        d = self.d
        assert d[:4] == b'\x7fELF'
        (self.e_type, self.e_machine, _v, _e, _p, self.e_shoff, _f,
         _ehsz, _phes, _phn, self.e_shentsize, self.e_shnum, self.e_shstrndx) = \
            struct.unpack_from('<HHIIIIIHHHHHH', d, 16)
        self.sh = []
        for i in range(self.e_shnum):
            o = self.e_shoff + i*self.e_shentsize
            name,typ,flags,addr,off,size,link,info,align,entsize = struct.unpack_from('<10I', d, o)
            self.sh.append(dict(idx=i,name_off=name,type=typ,flags=flags,addr=addr,off=off,
                                size=size,link=link,info=info,align=align,entsize=entsize))
        shstr = self.sh[self.e_shstrndx]
        for s in self.sh:
            s['name'] = self.cstr(shstr['off'] + s['name_off'])
        self.byname = {s['name']: s for s in self.sh}
        # symtab
        st = self.byname.get('.symtab')
        self.syms = []
        if st:
            strtab = self.sh[st['link']]
            n = st['size']//16
            for i in range(n):
                o = st['off'] + i*16
                nm, val, sz, info, other, shndx = struct.unpack_from('<IIIBBH', d, o)
                self.syms.append(dict(i=i, name=self.cstr(strtab['off']+nm), value=val, size=sz,
                                      info=info, bind=info>>4, type=info&0xf, other=other, shndx=shndx))

    def cstr(self, off):
        e = self.d.index(b'\0', off)
        return self.d[off:e].decode('utf-8','replace')

    def sec(self, name):
        s = self.byname[name]
        return self.d[s['off']:s['off']+s['size']]

    def relocs(self, secname):
        """returns list of (offset, sym_index, type) for .rel<secname>"""
        s = self.byname.get('.rel'+secname)
        if not s: return []
        out=[]
        for i in range(s['size']//8):
            o=s['off']+i*8
            off, info = struct.unpack_from('<II', self.d, o)
            out.append((off, info>>8, info&0xff))
        return out

STB = {0:'LOCAL',1:'GLOBAL',2:'WEAK'}
STT = {0:'NOTYPE',1:'OBJECT',2:'FUNC',3:'SECTION',4:'FILE',6:'TLS'}

# ---- OEM inventory ---------------------------------------------------------
# Recovered from the shipped module's STT_FILE symbol grouping; see
# FINDINGS-oem-catalogue.md.  Address ranges are in the shipped .text.
OEM_FILES = {
    'ez_sc.c':          (0x92220, 0x9311c),
    'ez_wifi_config.c': (0x9311c, 0x94568),
}

def oem_funcs(e):
    """[(name, addr, size, file)] for the 46 OEM functions, .text order."""
    out = []
    for s in e.syms:
        if s['type'] != 2 or s['shndx'] >= len(e.sh):
            continue
        if e.sh[s['shndx']]['name'] != '.text':
            continue
        for f, (lo, hi) in OEM_FILES.items():
            if lo <= s['value'] < hi and s['bind'] != 0:
                out.append((s['name'], s['value'], s['size'], f))
    out.sort(key=lambda t: t[1])
    return out
