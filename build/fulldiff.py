#!/usr/bin/env python3
"""Whole-file byte-exactness scoreboard for the shipped 8188fu.ko vs a rebuild.

offsetdiff.py / bytecompare.py only score `.text` functions.  This scores the
*whole ELF file* -- every section, the symbol table (contents and order), every
relocation section and the string tables -- so the top-line number is
"bytes still differing on the way to a byte-identical file".

Two numbers are reported for every section:

  RAW         strict positional byte compare (plus |size delta|).  This is what
              byte-exactness literally means, but a single missing function
              shifts everything after it, so RAW is dominated by shift noise
              and is nearly useless for tracking convergence.
  STRUCTURAL  shift-tolerant.  Content is keyed by what it *is* (a function, a
              data object, a string, a relocation of symbol X at offset N inside
              function Y) rather than by where it sits, so the number counts
              real differences only.  It reaches 0 exactly when RAW does.

STRUCTURAL splits differing bytes into:
    missing     bytes of symbols/strings/entries present only in the shipped file
    extra       ... present only in ours
    resized     sum of |size delta| over symbols present in both
    content     bytes differing inside same-size symbols, excluding words a
                relocation covers
    reloc       bytes differing inside same-size symbols that a relocation covers
                (addends: pure link layout, they converge when everything else
                does -- reported but ranked separately)

Local symbol names carry GCC's uniquifier (`__func__.75858`).  That counter
shifts whenever anything above them in the same translation unit changes, so
names are compared with the trailing `.NNNN` stripped; the raw-name mismatch is
reported separately as `uniquifier renumbering`.

Self-contained ELF32-LE reader; no readelf, no pyelftools.

usage: build/fulldiff.py <shipped.ko> <rebuilt.ko> [options]

  --top N          rows in ranked lists (default 20)
  --section NAME   deep-dive one section (byte runs attributed to symbols)
  --strings        dump every .rodata.str1.1 string present in one file only
  --paths          restrict the string dump to path-like strings
  --syms           list symbol-table differences in full
  --brief          summary + ranked table only
"""
import sys, struct, collections, difflib, re

SHT = {0: 'NULL', 1: 'PROGBITS', 2: 'SYMTAB', 3: 'STRTAB', 4: 'RELA', 5: 'HASH',
       6: 'DYNAMIC', 7: 'NOTE', 8: 'NOBITS', 9: 'REL', 11: 'DYNSYM',
       0x70000001: 'ARM_EXIDX', 0x70000003: 'ARM_ATTRIBUTES'}
SHF = [(0x1, 'W'), (0x2, 'A'), (0x4, 'X'), (0x10, 'M'), (0x20, 'S'),
       (0x40, 'I'), (0x80, 'L'), (0x200, 'G'), (0x400, 'T'), (0x800, 'C')]
STB = {0: 'LOCAL', 1: 'GLOBAL', 2: 'WEAK'}
STT = {0: 'NOTYPE', 1: 'OBJECT', 2: 'FUNC', 3: 'SECTION', 4: 'FILE', 6: 'TLS'}
RTYPE = {0: 'NONE', 1: 'PC24', 2: 'ABS32', 3: 'REL32', 5: 'ABS16', 8: 'ABS8',
         10: 'THM_CALL', 28: 'CALL', 29: 'JUMP24', 40: 'V4BX', 42: 'PREL31',
         44: 'MOVW_ABS_NC', 45: 'MOVT_ABS'}

UNIQ = re.compile(r'\.\d+$')
CODE = ('.text', '.text.unlikely', '.init.text', '.exit.text')
DATA = ('.data', '.rodata', '.bss', '.gnu.linkonce.this_module')
MERGE = ('.rodata.str1.1', '.comment', '__ksymtab_strings')


def norm(name):
    return UNIQ.sub('', name)


def flagstr(f):
    return ''.join(c for bit, c in SHF if f & bit) or '-'


def n(x):
    return format(x, ',d')


class ELF:
    def __init__(self, path):
        self.path = path
        self.data = open(path, 'rb').read()
        d = self.data
        assert d[:4] == b'\x7fELF' and d[4] == 1 and d[5] == 1, path + ': not ELF32-LE'
        (self.e_type, self.e_machine, self.e_version, self.e_entry, self.e_phoff,
         self.e_shoff, self.e_flags, self.e_ehsize, self.e_phentsize, self.e_phnum,
         self.e_shentsize, self.e_shnum, self.e_shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', d, 16)
        self.ident = d[:16]
        self.sec = []
        for i in range(self.e_shnum):
            o = self.e_shoff + i * self.e_shentsize
            nm, ty, fl, ad, off, sz, lk, inf, al, es = struct.unpack_from('<10I', d, o)
            self.sec.append(dict(idx=i, nameoff=nm, type=ty, flags=fl, addr=ad, off=off,
                                 size=sz, link=lk, info=inf, align=al, entsize=es))
        shstr = self.sec[self.e_shstrndx]
        for s in self.sec:
            e = d.index(b'\0', shstr['off'] + s['nameoff'])
            s['name'] = d[shstr['off'] + s['nameoff']:e].decode('utf-8', 'replace')
            s['data'] = b'' if s['type'] == 8 else d[s['off']:s['off'] + s['size']]
        self.byname = {}
        for s in self.sec:
            self.byname.setdefault(s['name'], s)
        self._symtab()
        self._relcache = {}

    def _symtab(self):
        self.syms = []
        st = next((s for s in self.sec if s['type'] == 2), None)
        self.strtab = self.sec[st['link']]['data'] if st else b''
        if st is None:
            return
        strs = self.strtab
        for i in range(st['size'] // 16):
            nm, val, sz, info, other, shndx = struct.unpack_from('<IIIBBH', st['data'], i * 16)
            e = strs.index(b'\0', nm)
            name = strs[nm:e].decode('utf-8', 'replace')
            sec = {0: 'UND', 0xfff1: 'ABS', 0xfff2: 'COMMON'}.get(shndx)
            if sec is None:
                sec = (self.sec[shndx]['name'] if shndx < len(self.sec)
                       else '0x%x' % shndx)
            self.syms.append(dict(i=i, name=name, nname=norm(name), value=val, size=sz,
                                  info=info, bind=info >> 4, type=info & 0xf,
                                  other=other, shndx=shndx, sec=sec))

    def rels(self, name):
        """[(offset, type, target-symbol-name)] for the relocations applying to section `name`"""
        if name in self._relcache:
            return self._relcache[name]
        out = []
        for s in self.sec:
            if s['type'] == 9 and s['info'] < len(self.sec) and self.sec[s['info']]['name'] == name:
                for i in range(s['size'] // 8):
                    off, info = struct.unpack_from('<II', s['data'], i * 8)
                    si, ty = info >> 8, info & 0xff
                    out.append((off, ty, self.syms[si]['name'] if si < len(self.syms) else '?'))
        self._relcache[name] = out
        return out

    def secsyms(self, name):
        """{normalised name: [sym, ...]} for the sized symbols living in section `name`"""
        d = collections.defaultdict(list)
        for s in self.syms:
            if s['sec'] == name and s['size'] and s['type'] in (1, 2):
                d[s['nname']].append(s)
        for v in d.values():
            v.sort(key=lambda s: s['value'])
        return d


def runs(x, y):
    """(differing bytes, [(start, len)]) over the common prefix"""
    m = min(len(x), len(y))
    d, rr, i = 0, [], 0
    while i < m:
        if x[i] != y[i]:
            j = i
            while j < m and x[j] != y[j]:
                j += 1
            rr.append((i, j - i))
            d += j - i
            i = j
        else:
            i += 1
    return d, rr


def relmask(E, secname, base, size):
    """bytearray(size): 1 where a relocation covers the byte"""
    m = bytearray(size)
    for off, ty, tgt in E.rels(secname):
        if base <= off < base + size:
            k = off - base
            m[k:k + 4] = b'\1' * min(4, size - k)
    return m


# --------------------------------------------------------------------------
# structural scoring
# --------------------------------------------------------------------------
class Score:
    """missing/extra/resized/content are independent differences and are summed
    into `total`; reloc (addends) and derived (differences that are a mechanical
    consequence of something already counted, e.g. GCC's local-symbol
    uniquifier renumbering) are reported but excluded from `total`."""
    __slots__ = ('missing', 'extra', 'resized', 'content', 'reloc', 'derived',
                 'branch', 'note')

    def __init__(self):
        self.missing = self.extra = self.resized = self.content = self.reloc = 0
        self.derived = self.branch = 0
        self.note = ''

    @property
    def total(self):
        return self.missing + self.extra + self.resized + self.content

    def line(self):
        p = []
        for k in ('missing', 'extra', 'resized', 'content'):
            v = getattr(self, k)
            if v:
                p.append('%s %s' % (k, n(v)))
        if self.reloc:
            p.append('(+%s reloc addends)' % n(self.reloc))
        if self.branch:
            p.append('(+%s branch displacements)' % n(self.branch))
        if self.derived:
            p.append('(+%s derived)' % n(self.derived))
        return ', '.join(p) or 'identical'


def _union(iv):
    """total bytes covered by [(start, end)] intervals, aliases counted once"""
    tot, cur_e = 0, -1
    for a, b in sorted(iv):
        if b <= cur_e:
            continue
        tot += b - max(a, cur_e)
        cur_e = b
    return tot


def _pair(la, lb, da, db, nobits):
    """pair up same-named symbols: exact-content matches first, then by address.

    GCC's uniquifier (`__func__.75858`) is stripped before comparing names, so a
    single normalised name can cover 200 different string constants; pairing them
    by address would manufacture hundreds of bogus size differences."""
    if len(la) == 1 and len(lb) == 1:
        return [(la[0], lb[0])], [], []
    if nobits:
        k = min(len(la), len(lb))
        return list(zip(la, lb)), la[k:], lb[k:]
    idx = collections.defaultdict(list)
    for y in lb:
        idx[db[y['value']:y['value'] + y['size']]].append(y)
    pairs, rest_a = [], []
    for x in la:
        c = da[x['value']:x['value'] + x['size']]
        if idx.get(c):
            pairs.append((x, idx[c].pop(0)))
        else:
            rest_a.append(x)
    rest_b = sorted((y for v in idx.values() for y in v), key=lambda s: s['value'])
    k = min(len(rest_a), len(rest_b))
    pairs += list(zip(rest_a, rest_b))
    return pairs, rest_a[k:], rest_b[k:]


def score_symbolic(A, B, name, detail=None):
    """symbol-attributed diff of a code/data section"""
    sc = Score()
    fa, fb = A.secsyms(name), B.secsyms(name)
    da, db = A.byname[name]['data'], B.byname[name]['data']
    nobits = A.byname[name]['type'] == 8
    code = name in CODE
    cov_a = _union([(s['value'], s['value'] + s['size']) for l in fa.values() for s in l])
    cov_b = _union([(s['value'], s['value'] + s['size']) for l in fb.values() for s in l])
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    sc.missing = sum(s['size'] for k in only_a for s in fa[k])
    sc.extra = sum(s['size'] for k in only_b for s in fb[k])
    sized, diffd, ident = [], [], 0
    leftover_a, leftover_b = [], []
    for k in sorted(set(fa) & set(fb)):
        pairs, ra, rb = _pair(fa[k], fb[k], da, db, nobits)
        sc.missing += sum(s['size'] for s in ra)
        sc.extra += sum(s['size'] for s in rb)
        if ra:
            leftover_a.append((k, sum(s['size'] for s in ra), len(ra)))
        if rb:
            leftover_b.append((k, sum(s['size'] for s in rb), len(rb)))
        for x, y in pairs:
            if x['size'] != y['size']:
                sized.append((k, x['size'], y['size']))
                sc.resized += abs(x['size'] - y['size'])
                continue
            if nobits:
                ident += x['size']
                continue
            bx = da[x['value']:x['value'] + x['size']]
            by = db[y['value']:y['value'] + y['size']]
            if bx == by:
                ident += x['size']
                continue
            ma = relmask(A, name, x['value'], x['size'])
            mb = relmask(B, name, y['value'], y['size'])
            c = r = br = 0
            for i in range(len(bx)):
                if bx[i] != by[i]:
                    if ma[i] or mb[i]:
                        r += 1
                    else:
                        c += 1
            if code and c:                 # re-classify whole words
                c = 0
                for i in range(0, len(bx) & ~3, 4):
                    wa = struct.unpack_from('<I', bx, i)[0]
                    wb = struct.unpack_from('<I', by, i)[0]
                    if wa == wb or ma[i] or mb[i]:
                        continue
                    if (wa >> 24) == (wb >> 24) and ((wa >> 25) & 7) == 5:
                        br += 4            # B/BL: only the imm24 differs => layout
                    else:
                        c += 4
            sc.content += c
            sc.reloc += r
            sc.branch += br
            diffd.append((k, x['size'], c, r, br))
    ua, ub = A.byname[name]['size'] - cov_a, B.byname[name]['size'] - cov_b
    ba = sum(s['size'] for k in only_a for s in fa[k]) + sum(x[1] for x in leftover_a)
    bb = sum(s['size'] for k in only_b for s in fb[k]) + sum(x[1] for x in leftover_b)
    la = [(k, sum(s['size'] for s in fa[k]), len(fa[k])) for k in only_a] + leftover_a
    lb = [(k, sum(s['size'] for s in fb[k]), len(fb[k])) for k in only_b] + leftover_b
    sc.note = ('%d/%d symbol names shared; unmatched symbols: %d shipped-only (%s bytes), '
               '%d ours-only (%s bytes); bytes outside any sized symbol: %s vs %s'
               % (len(set(fa) & set(fb)), len(fa), sum(x[2] for x in la), n(ba),
                  sum(x[2] for x in lb), n(bb), n(ua), n(ub)))
    if detail is not None:
        detail.update(only_a=sorted(la, key=lambda x: -x[1]), only_b=sorted(lb, key=lambda x: -x[1]),
                      sized=sized, diffd=diffd, ident=ident, fa=fa, fb=fb, unattr=(ua, ub))
    sc.missing += max(0, ua - ub)
    sc.extra += max(0, ub - ua)
    return sc


def score_merge(A, B, name, detail=None):
    """multiset diff of a SHF_MERGE|SHF_STRINGS section"""
    sc = Score()
    ca = collections.Counter(x for x in A.byname[name]['data'].split(b'\0') if x)
    cb = collections.Counter(x for x in B.byname[name]['data'].split(b'\0') if x)
    oa, ob = ca - cb, cb - ca
    sc.missing = sum((len(k) + 1) * v for k, v in oa.items())
    sc.extra = sum((len(k) + 1) * v for k, v in ob.items())
    sc.note = ('%d distinct shipped / %d ours / %d shared; %d strings only in shipped, '
               '%d only in ours' % (len(ca), len(cb), len(set(ca) & set(cb)),
                                    sum(oa.values()), sum(ob.values())))
    if detail is not None:
        detail.update(only_a=oa, only_b=ob, ca=ca, cb=cb)
    return sc


def relkey(E, target):
    """relocations of section `target`, keyed shift-tolerantly by owning symbol"""
    if E.byname[target]['type'] == 0x70000001:      # ARM_EXIDX: no symbols live
        _, off2fn = _exidx_entries(E, target)       # there, key by the function
        keys = collections.Counter()                # the entry describes
        for off, ty, tgt in E.rels(target):
            keys[(off2fn.get(off - off % 8), off % 8, ty, norm(tgt))] += 1
        return keys, 0
    syms = sorted([s for s in E.syms if s['sec'] == target and s['size']],
                  key=lambda s: s['value'])
    starts = [s['value'] for s in syms]
    import bisect
    keys = collections.Counter()
    orphan = 0
    for off, ty, tgt in E.rels(target):
        i = bisect.bisect_right(starts, off) - 1
        if i >= 0 and off < syms[i]['value'] + syms[i]['size']:
            keys[(syms[i]['nname'], off - syms[i]['value'], ty, norm(tgt))] += 1
        else:
            orphan += 1
            keys[(None, off, ty, norm(tgt))] += 1
    return keys, orphan


def score_rel(A, B, relname, target, detail=None):
    sc = Score()
    ka, ora = relkey(A, target)
    kb, orb = relkey(B, target)
    oa, ob = ka - kb, kb - ka
    sc.missing = 8 * sum(oa.values())
    sc.extra = 8 * sum(ob.values())
    sc.note = ('%d vs %d entries, %d unmatched shipped / %d unmatched ours '
               '(%d/%d outside any sized symbol)'
               % (sum(ka.values()), sum(kb.values()), sum(oa.values()), sum(ob.values()), ora, orb))
    if detail is not None:
        detail.update(only_a=oa, only_b=ob)
    return sc


def _exidx_entries(E, name):
    """{owning .text symbol: unwind word} -- the entry's first word is a PREL31
    whose stored addend is exactly the target's offset in the code section."""
    sec = E.byname[name]
    d = sec['data']
    tgt = E.sec[sec['link']]['name'] if sec['link'] < len(E.sec) else '.text'
    syms = sorted([s for s in E.syms if s['sec'] == tgt and s['size'] and s['type'] == 2],
                  key=lambda s: s['value'])
    starts = [s['value'] for s in syms]
    import bisect
    out, off2fn = {}, {}
    for i in range(len(d) // 8):
        o = i * 8
        w0 = struct.unpack_from('<i', d, o)[0]
        j = bisect.bisect_right(starts, w0) - 1
        fn = (syms[j]['nname'] if j >= 0 and w0 < syms[j]['value'] + syms[j]['size']
              else '?0x%x' % w0)
        out[fn] = d[o + 4:o + 8]
        off2fn[o] = fn
    return out, off2fn


def score_exidx(A, B, name, target, detail=None):
    """ARM unwind index: one 8-byte entry per function, keyed by that function"""
    sc = Score()
    ea, _ = _exidx_entries(A, name)
    eb, _ = _exidx_entries(B, name)
    oa, ob = set(ea) - set(eb), set(eb) - set(ea)
    sc.missing = 8 * len(oa)
    sc.extra = 8 * len(ob)
    bad = [k for k in set(ea) & set(eb) if ea[k] != eb[k]]
    sc.content = 4 * len(bad)
    sc.note = ('%d vs %d entries; %d shipped-only, %d ours-only, %d differing unwind words'
               % (len(ea), len(eb), len(oa), len(ob), len(bad)))
    if detail is not None:
        detail.update(only_a=sorted(oa), only_b=sorted(ob), bad=sorted(bad))
    return sc


def score_symtab(A, B, detail=None):
    """symbol table: entries keyed by everything but st_value (which is layout).

    Entries that agree on st_size too are paired first, so a section full of
    same-named locals (`__func__`) does not manufacture size differences."""
    sc = Score()
    key = lambda s: (s['nname'], s['sec'], s['type'], s['bind'], s['other'])
    fa = collections.Counter((key(s), s['size']) for s in A.syms)
    fb = collections.Counter((key(s), s['size']) for s in B.syms)
    ra, rb = fa - fb, fb - fa            # entries left over after exact pairing
    la = collections.Counter(k for (k, sz), v in ra.items() for _ in range(v))
    lb = collections.Counter(k for (k, sz), v in rb.items() for _ in range(v))
    szdiff = sum((la & lb).values())      # same identity, different st_size
    sc.content = 4 * szdiff
    sc.missing = 16 * sum((la - lb).values())
    sc.extra = 16 * sum((lb - la).values())
    raw_a = collections.Counter(s['name'] for s in A.syms)
    raw_b = collections.Counter(s['name'] for s in B.syms)
    sc.derived = 0
    sc.note = ('%d vs %d entries; %d shipped-only, %d ours-only, %d differing only in '
               'st_size; %d entries differ only by GCC uniquifier renumbering'
               % (len(A.syms), len(B.syms), sum((la - lb).values()), sum((lb - la).values()),
                  szdiff, sum((raw_a - raw_b).values()) - sum((la - lb).values())))
    if detail is not None:
        detail.update(only_a=la - lb, only_b=lb - la, szdiff=szdiff)
    return sc


def score_strtab(A, B, name):
    sc = Score()
    sa = set(x for x in A.byname[name]['data'].split(b'\0') if x)
    sb = set(x for x in B.byname[name]['data'].split(b'\0') if x)
    na_ = set(norm(x.decode('utf-8', 'replace')) for x in sa)
    nb_ = set(norm(x.decode('utf-8', 'replace')) for x in sb)
    sc.missing = sum(len(k) + 1 for k in na_ - nb_)
    sc.extra = sum(len(k) + 1 for k in nb_ - na_)
    raw = sum(len(k) + 1 for k in sa - sb) + sum(len(k) + 1 for k in sb - sa)
    sc.derived = raw - sc.missing - sc.extra
    sc.note = ('%d vs %d strings; %d shipped-only, %d ours-only; after stripping GCC '
               'uniquifiers %d / %d (the rest is renumbering of local symbols)'
               % (len(sa), len(sb), len(sa - sb), len(sb - sa), len(na_ - nb_), len(nb_ - na_)))
    return sc


def score_positional(A, B, name):
    sc = Score()
    x, y = A.byname[name]['data'], B.byname[name]['data']
    if A.byname[name]['type'] == 8:
        d = abs(A.byname[name]['size'] - B.byname[name]['size'])
        sc.missing = max(0, A.byname[name]['size'] - B.byname[name]['size'])
        sc.extra = max(0, B.byname[name]['size'] - A.byname[name]['size'])
        sc.note = 'NOBITS, size only'
        return sc
    c, rr = runs(x, y)
    sc.content = c
    sc.missing = max(0, len(x) - len(y))
    sc.extra = max(0, len(y) - len(x))
    sc.note = '%d differing bytes in %d runs' % (c, len(rr))
    return sc


# --------------------------------------------------------------------------
def main():
    args = sys.argv[1:]
    o = {'top': 20, 'section': None, 'strings': False, 'paths': False,
         'syms': False, 'brief': False}
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--top':
            i += 1
            o['top'] = int(args[i])
        elif a == '--section':
            i += 1
            o['section'] = args[i]
        elif a in ('--strings', '--paths', '--syms', '--brief'):
            o[a[2:]] = True
        elif a in ('-h', '--help'):
            print(__doc__)
            return
        else:
            pos.append(a)
        i += 1
    if len(pos) != 2:
        print(__doc__)
        sys.exit(2)
    A, B = ELF(pos[0]), ELF(pos[1])
    top = o['top']
    out = []
    P = out.append
    P('shipped : %s  %s bytes' % (pos[0], n(len(A.data))))
    P('ours    : %s  %s bytes  (%+d)' % (pos[1], n(len(B.data)), len(B.data) - len(A.data)))
    m = min(len(A.data), len(B.data))
    cp = 0
    while cp < m and A.data[cp] == B.data[cp]:
        cp += 1
    P('raw file: identical for the first %s bytes' % n(cp))
    fields = ['ident', 'e_type', 'e_machine', 'e_version', 'e_entry', 'e_phoff',
              'e_flags', 'e_ehsize', 'e_shentsize', 'e_shnum', 'e_shstrndx']
    bad = [(f, getattr(A, f), getattr(B, f)) for f in fields if getattr(A, f) != getattr(B, f)]
    P('ELF header: %s' % ('identical (e_flags=0x%x, %d sections)' % (A.e_flags, A.e_shnum)
                          if not bad else '%d field(s) differ: %s' % (len(bad), bad)))

    # ---------------- section inventory ----------------
    na = [s['name'] for s in A.sec]
    nb = [s['name'] for s in B.sec]
    if not o['brief']:
        P('')
        P('== SECTION INVENTORY  (shipped %d, ours %d)' % (len(na), len(nb)))
        if na == nb:
            P('   names, order: IDENTICAL')
        else:
            sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag != 'equal':
                    P('   %-7s shipped[%d:%d]=%s  ours[%d:%d]=%s'
                      % (tag, i1, i2, na[i1:i2], j1, j2, nb[j1:j2]))
        P('')
        P('   %-28s %-14s %5s %3s %3s %10s %10s %8s' %
          ('name', 'type', 'flags', 'al', 'es', 'shipped', 'ours', 'delta'))
        for s in A.sec:
            t = B.byname.get(s['name'])
            if t is None:
                P('   %-28s %-14s %5s %3d %3d %10s %10s %8s  ONLY IN SHIPPED'
                  % (s['name'] or '(null)', SHT.get(s['type'], hex(s['type'])),
                     flagstr(s['flags']), s['align'], s['entsize'], n(s['size']), '-', '-'))
                continue
            mm = [k for k in ('type', 'flags', 'align', 'entsize') if s[k] != t[k]]
            P('   %-28s %-14s %5s %3d %3d %10s %10s %8s%s'
              % (s['name'] or '(null)', SHT.get(s['type'], hex(s['type'])),
                 flagstr(s['flags']), s['align'], s['entsize'], n(s['size']), n(t['size']),
                 ('%+d' % (t['size'] - s['size'])) if t['size'] != s['size'] else '=',
                 ('   HDR-DIFF: ' + ','.join(mm)) if mm else ''))
        for s in B.sec:
            if s['name'] not in A.byname:
                P('   %-28s %-14s %5s %3d %3d %10s %10s %8s  ONLY IN OURS'
                  % (s['name'] or '(null)', SHT.get(s['type'], hex(s['type'])),
                     flagstr(s['flags']), s['align'], s['entsize'], '-', n(s['size']), '-'))

    # ---------------- score every section ----------------
    rank = []            # (name, structural, raw, Score)
    details = {}
    for s in A.sec:
        nm = s['name']
        if nm == '':
            continue
        t = B.byname.get(nm)
        if t is None:
            sc = Score()
            sc.missing = s['size']
            sc.note = 'section absent from ours'
            rank.append((nm, sc, s['size']))
            continue
        det = {}
        if nm in CODE or nm in DATA:
            sc = score_symbolic(A, B, nm, det)
        elif nm in MERGE:
            sc = score_merge(A, B, nm, det)
        elif s['type'] == 9:
            tgt = A.sec[s['info']]['name'] if s['info'] < len(A.sec) else None
            sc = score_rel(A, B, nm, tgt, det) if tgt else score_positional(A, B, nm)
        elif s['type'] == 0x70000001:
            tgt = A.sec[s['link']]['name'] if s['link'] < len(A.sec) else None
            sc = score_exidx(A, B, nm, tgt, det)
        elif s['type'] == 2:
            sc = score_symtab(A, B, det)
        elif s['type'] == 3:
            sc = score_strtab(A, B, nm)
        else:
            sc = score_positional(A, B, nm)
        details[nm] = det
        rawc, _ = runs(s['data'], t['data'])
        raw = rawc + abs(s['size'] - t['size'])
        rank.append((nm, sc, raw))

    # ---------------- detail passes ----------------
    if not o['brief']:
        for nm in CODE + DATA:
            if nm not in A.byname or nm not in B.byname:
                continue
            d = details.get(nm) or {}
            if not d:
                continue
            sc = next(x[1] for x in rank if x[0] == nm)
            P('')
            P('== %s  (%s vs %s bytes, %+d)  %s'
              % (nm, n(A.byname[nm]['size']), n(B.byname[nm]['size']),
                 B.byname[nm]['size'] - A.byname[nm]['size'], sc.line()))
            P('   %s' % sc.note)
            for label, l in (('shipped', d['only_a']), ('ours', d['only_b'])):
                if l:
                    P('   unmatched symbols only in %s (%d, %s bytes): %s%s'
                      % (label, sum(x[2] for x in l), n(sum(x[1] for x in l)),
                         ', '.join('%s%s' % (k, '' if c == 1 else ' x%d' % c)
                                   for k, b, c in l[:top]),
                         ' ... +%d' % (len(l) - top) if len(l) > top else ''))
            if d['sized']:
                P('   size-differing (%d):' % len(d['sized']))
                for k, x, y in sorted(d['sized'], key=lambda t: -abs(t[1] - t[2]))[:top]:
                    P('     %-46s %7d -> %-7d %+d' % (k[:46], x, y, y - x))
                if len(d['sized']) > top:
                    P('     ... +%d more' % (len(d['sized']) - top))
            if d['diffd']:
                nz = [x for x in d['diffd'] if x[2]]
                P('   same-size but differing: %d symbols; %s content bytes in %d of them, '
                  '%s reloc-addend bytes, %s branch-displacement bytes'
                  % (len(d['diffd']), n(sum(x[2] for x in d['diffd'])), len(nz),
                     n(sum(x[3] for x in d['diffd'])), n(sum(x[4] for x in d['diffd']))))
                for k, sz, c, r, br in sorted(d['diffd'], key=lambda t: -t[2])[:top]:
                    if c:
                        P('     %-46s size %7d  %5d content + %d reloc + %d branch'
                          % (k[:46], sz, c, r, br))
                if len(nz) > top:
                    P('     ... +%d more with content differences' % (len(nz) - top))

        # strings
        for nm in MERGE:
            if nm not in A.byname or nm not in B.byname:
                continue
            d = details[nm]
            sc = next(x[1] for x in rank if x[0] == nm)
            P('')
            P('== %s  (%s vs %s bytes, %+d)  %s'
              % (nm, n(A.byname[nm]['size']), n(B.byname[nm]['size']),
                 B.byname[nm]['size'] - A.byname[nm]['size'], sc.line()))
            P('   %s' % sc.note)
            ispath = lambda s: b'/' in s and (b'.c' in s or b'.h' in s)
            for label, cnt in (('shipped-only', d['only_a']), ('ours-only', d['only_b'])):
                items = sorted(cnt.items(), key=lambda kv: -len(kv[0]))
                paths = [(k, v) for k, v in items if ispath(k)]
                rest = [(k, v) for k, v in items if not ispath(k)]
                P('   %s: %d path-like, %d other' % (label, len(paths), len(rest)))
                show = paths if o['paths'] else paths + rest
                lim = len(show) if o['strings'] else top
                for k, v in show[:lim]:
                    P('     %s%s' % (('x%d ' % v) if v > 1 else '',
                                     k.decode('utf-8', 'replace').replace('\n', '\\n')[:160]))
                if len(show) > lim:
                    P('     ... +%d more' % (len(show) - lim))

        # symtab
        P('')
        sa, sb = A.byname['.symtab'], B.byname['.symtab']
        sc = next(x[1] for x in rank if x[0] == '.symtab')
        P('== .symtab  (%s vs %s bytes, %+d; sh_info %d vs %d)  %s'
          % (n(sa['size']), n(sb['size']), sb['size'] - sa['size'], sa['info'], sb['info'], sc.line()))
        P('   %s' % sc.note)
        d = details['.symtab']
        for label, c in (('shipped-only', d['only_a']), ('ours-only', d['only_b'])):
            items = sorted(c.items())
            lim = len(items) if o['syms'] else top
            for k, v in items[:lim]:
                P('     %-12s %-46s %-18s %s/%s%s' % (label, k[0][:46], k[1],
                                                      STT.get(k[2], k[2]), STB.get(k[3], k[3]),
                                                      '' if v == 1 else ' x%d' % v))
            if len(items) > lim:
                P('     %-12s ... +%d more' % (label, len(items) - lim))
        # attribute diffs among shared names
        da = {s['name']: s for s in A.syms if s['name']}
        db = {s['name']: s for s in B.syms if s['name']}
        attr = []
        for k in sorted(set(da) & set(db)):
            x, y = da[k], db[k]
            w = []
            if x['size'] != y['size']:
                w.append('st_size %d->%d' % (x['size'], y['size']))
            if x['info'] != y['info']:
                w.append('st_info %s/%s->%s/%s' % (STT.get(x['type']), STB.get(x['bind']),
                                                   STT.get(y['type']), STB.get(y['bind'])))
            if x['other'] != y['other']:
                w.append('st_other %d->%d' % (x['other'], y['other']))
            if x['sec'] != y['sec']:
                w.append('shndx %s->%s' % (x['sec'], y['sec']))
            if w:
                attr.append((k, '; '.join(w)))
        P('   shared names differing in st_size/st_info/st_other/shndx: %d' % len(attr))
        lim = len(attr) if o['syms'] else top
        for k, w in attr[:lim]:
            P('     %-46s %s' % (k[:46], w))
        if len(attr) > lim:
            P('     ... +%d more' % (len(attr) - lim))
        # order
        sm = difflib.SequenceMatcher(None, [s['name'] for s in A.syms],
                                     [s['name'] for s in B.syms], autojunk=False)
        ops = sm.get_opcodes()
        eq = sum(i2 - i1 for t, i1, i2, _, _ in ops if t == 'equal')
        P('   order (raw names): LCS keeps %d/%d shipped entries, %d edit blocks'
          % (eq, len(A.syms), sum(1 for x in ops if x[0] != 'equal')))
        ra = [s['nname'] for s in A.syms]
        rb = [s['nname'] for s in B.syms]
        common = set(ra) & set(rb)
        fa = [x for x in ra if x in common]
        fb = [x for x in rb if x in common]
        P('   order (uniquifier-stripped, shared names only): %s'
          % ('IDENTICAL' if fa == fb else 'DIFFERS'))
        if fa != fb:
            sm2 = difflib.SequenceMatcher(None, fa, fb, autojunk=False)
            bad2 = [x for x in sm2.get_opcodes() if x[0] != 'equal']
            P('     %d reordering blocks; first at shipped index %d: %s | %s'
              % (len(bad2), bad2[0][1], fa[bad2[0][1]:bad2[0][1] + 3], fb[bad2[0][3]:bad2[0][3] + 3]))

        # relocations
        P('')
        P('== RELOCATIONS')
        P('   %-30s %8s %8s %7s  %s' % ('section', 'shipped', 'ours', 'delta', 'structural'))
        for s in A.sec:
            if s['type'] != 9:
                continue
            t = B.byname.get(s['name'])
            sc = next((x[1] for x in rank if x[0] == s['name']), None)
            P('   %-30s %8d %8d %7s  %s'
              % (s['name'], s['size'] // 8, (t['size'] // 8) if t else 0,
                 ('%+d' % ((t['size'] - s['size']) // 8)) if t and t['size'] != s['size'] else '=',
                 sc.note if sc else 'ABSENT'))
        # exidx / strtab one-liners
        for s in A.sec:
            if s['type'] in (0x70000001, 3) or s['name'] in ('.ARM.attributes', '.note.gnu.build-id',
                                                             '.modinfo', '__param', '__ksymtab'):
                t = B.byname.get(s['name'])
                sc = next((x[1] for x in rank if x[0] == s['name']), None)
                if t is None or sc is None:
                    continue
                P('')
                P('== %s  (%s vs %s bytes, %+d)  %s'
                  % (s['name'], n(s['size']), n(t['size']), t['size'] - s['size'], sc.line()))
                P('   %s' % sc.note)

    # ---------------- deep dive ----------------
    if o['section']:
        nm = o['section']
        sa, sb = A.byname.get(nm), B.byname.get(nm)
        P('')
        P('== DEEP DIVE %s' % nm)
        if not sa or not sb:
            P('   missing from one file')
        else:
            c, rr = runs(sa['data'], sb['data'])
            P('   sizes %s / %s; RAW %s differing bytes in %d runs over the common prefix'
              % (n(sa['size']), n(sb['size']), n(c), len(rr)))
            syms = sorted([s for s in A.syms if s['sec'] == nm and s['size']],
                          key=lambda s: s['value'])
            import bisect
            starts = [s['value'] for s in syms]

            def owner(off):
                i = bisect.bisect_right(starts, off) - 1
                if i >= 0 and off < syms[i]['value'] + syms[i]['size']:
                    return syms[i]['name']
                return '(unattributed)'
            by = collections.Counter()
            for off, ln in rr:
                by[owner(off)] += ln
            for k, v in by.most_common(top):
                P('     %-46s %s bytes' % (k[:46], n(v)))
            if len(by) > top:
                P('     ... +%d more owners' % (len(by) - top))

    # ---------------- summary ----------------
    tot_s = sum(sc.total for _, sc, _ in rank)
    tot_r = sum(r for _, _, r in rank)
    tot_rel = sum(sc.reloc for _, sc, _ in rank)
    tot_br = sum(sc.branch for _, sc, _ in rank)
    P('')
    P('== RANKED: where the remaining bytes are  (structural, shift-tolerant)')
    P('   %-30s %11s %6s %11s  %s' % ('section', 'structural', 'share', 'raw', 'breakdown'))
    for nm, sc, raw in sorted(rank, key=lambda r: (-r[1].total, -r[2])):
        if sc.total == 0 and sc.reloc == 0 and o['brief']:
            continue
        P('   %-30s %11s %5.1f%% %11s  %s'
          % (nm, n(sc.total), 100.0 * sc.total / max(tot_s, 1), n(raw), sc.line()))
    P('')
    P('== SUMMARY')
    P('   STRUCTURAL  %s bytes differ (%.3f%% of the shipped %s)'
      % (n(tot_s), 100.0 * tot_s / len(A.data), n(len(A.data))))
    P('   RAW         %s bytes differ positionally (%.2f%%) -- includes shift noise'
      % (n(tot_r), 100.0 * tot_r / len(A.data)))
    P('   link layout inside otherwise-matching symbols: %s bytes of relocation addends, '
      '%s bytes of B/BL displacements' % (n(tot_rel), n(tot_br)))
    P('   byte-identical sections: %d/%d'
      % (sum(1 for _, sc, raw in rank if raw == 0), len(rank)))
    print('\n'.join(out))


if __name__ == '__main__':
    main()
