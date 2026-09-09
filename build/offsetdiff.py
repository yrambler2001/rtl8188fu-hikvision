#!/usr/bin/env python3
"""Extract per-instruction operand differences between the shipped 8188fu.ko and a rebuild.

Beyond bytecompare.py this:
  * also masks PC-relative literal loads (ldr rX,[pc,#N]) -- those track literal-pool
    layout, not struct layout, so they are noise for diagnosis
  * decodes ldr/str imm12, ldrh/strh/ldrd imm8, and add/sub immediates
  * emits a histogram of (rebuilt_offset -> shipped_offset) pairs, which is the
    oracle for recovering vendor kernel struct layouts.

usage: build/offsetdiff.py <shipped.ko> <rebuilt.ko> [--pairs N] [--fn NAME]
"""
import subprocess, re, struct, sys, collections

READELF = 'arm-none-eabi-readelf'

def sections(f):
    out = subprocess.run([READELF,'-SW',f],capture_output=True,text=True).stdout
    return {int(m.group(1)):{'name':m.group(2),'off':int(m.group(4),16)} for m in
            re.finditer(r'\[\s*(\d+)\]\s+(\S+)\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',out)}

def symbols(f, kind='FUNC'):
    out = subprocess.run([READELF,'-sW',f],capture_output=True,text=True).stdout
    d={}
    for line in out.splitlines():
        p=line.split()
        if len(p)>=8 and p[3]==kind and p[6].isdigit():
            try: d[p[7]]=(int(p[1],16),int(p[2]),int(p[6]))
            except ValueError: pass
    return d

def relocs(f):
    out = subprocess.run([READELF,'-rW',f],capture_output=True,text=True).stdout
    secs=sections(f); n2i={v['name']:k for k,v in secs.items()}; cur=None; d={}
    for line in out.splitlines():
        m=re.match(r"Relocation section '(\S+)'",line)
        if m: cur=n2i.get(m.group(1).replace('.rel','',1)); d.setdefault(cur,set()); continue
        p=line.split()
        if cur is not None and len(p)>=2 and re.fullmatch(r'[0-9a-f]{8}',p[0]):
            d[cur].add(int(p[0],16))
    return d

def load(f): return open(f,'rb').read(), sections(f), symbols(f), relocs(f)

def raw(L,name):
    data,secs,syms,rels = L
    val,size,ndx = syms[name]
    if ndx not in secs or size==0: return None,None
    off=secs[ndx]['off']+val
    b=bytearray(data[off:off+size])
    mask=bytearray(len(b))                     # 1 => byte is link-layout, ignore
    for r in rels.get(ndx,()):
        if val<=r<val+size: mask[r-val:r-val+4]=b'\1\1\1\1'
    return bytes(b), mask

# ---- ARM A1 decoders -------------------------------------------------------
def dec(w):
    """return (kind, rn, imm, keyfields) or None"""
    op = (w>>25)&0x7
    if op==0b010:                                   # ldr/str immediate
        rn=(w>>16)&0xF; imm=w&0xFFF
        return ('ldst12', rn, imm, w & ~0xFFF)
    if op==0b000 and (w>>22)&1 and (w>>4&0xF) in (0xB,0xD,0xF,0x9):
        # ldrh/strh/ldrd/strd/ldrsb/ldrsh immediate (and swp/mul share space: filter)
        if (w>>4&0xF)==0x9: return None             # mul/swp, not a load
        rn=(w>>16)&0xF; imm=((w>>8)&0xF)<<4 | (w&0xF)
        return ('ldst8', rn, imm, w & ~0xF0F)
    if op==0b001:                                   # data-processing immediate
        oc=(w>>21)&0xF
        if oc in (0b0100,0b0010):                   # add, sub
            rot=((w>>8)&0xF)*2; imm8=w&0xFF
            imm=((imm8>>rot)|(imm8<<(32-rot)))&0xFFFFFFFF if rot else imm8
            return ('addsub', (w>>16)&0xF, imm, w & ~0xFFF)
    return None

def isbranch(w): return ((w>>25)&0x7)==0b101

def main():
    shipped, rebuilt = sys.argv[1], sys.argv[2]
    want_fn = None; npairs=40
    if '--fn' in sys.argv: want_fn = sys.argv[sys.argv.index('--fn')+1]
    if '--pairs' in sys.argv: npairs = int(sys.argv[sys.argv.index('--pairs')+1])
    A=load(shipped); B=load(rebuilt)
    total=sum(s for _,s,_ in A[2].values()); nfun=len(A[2])
    exact=exact_b=sized=0
    kinds=collections.Counter(); pairs=collections.Counter()
    pairfns=collections.defaultdict(set); diffn=0
    per_fn_res=collections.Counter()
    for k in sorted(A[2]):
        if want_fn and k!=want_fn: continue
        if k not in B[2] or A[2][k][1]!=B[2][k][1] or A[2][k][1]==0: continue
        sized+=1
        (a,ma),(b,mb) = raw(A,k), raw(B,k)
        if a is None or b is None: continue
        n=min(len(a),len(b)); res=0
        loc=[]
        for i in range(0,n-3,4):
            if ma[i] or mb[i]: continue
            wa=struct.unpack_from('<I',a,i)[0]; wb=struct.unpack_from('<I',b,i)[0]
            if wa==wb: continue
            if isbranch(wa) and isbranch(wb) and (wa&0xFF000000)==(wb&0xFF000000):
                continue                                     # intra-.text branch target
            da,db = dec(wa), dec(wb)
            if da and db and da[0]==db[0] and da[3]==db[3]:
                if da[1]==15 or db[1]==15:
                    kinds['pc-relative literal load (literal-pool layout)']+=1
                    continue                                 # noise, not a real diff
                kinds[f'{da[0]} immediate differs (STRUCT LAYOUT)']+=1
                pairs[(db[2],da[2])]+=1                      # (rebuilt -> shipped)
                pairfns[(db[2],da[2])].add(k)
                res+=1; loc.append((i,hex(wb),hex(wa),db[2],da[2])); continue
            ldst=((wa>>26)&0x3)==0b01
            if ldst: kinds['ldr/str, other field']+=1
            elif (wa&0x0FF00000)==(wb&0x0FF00000): kinds['same opcode, operand differs']+=1
            else: kinds['different opcode']+=1
            res+=1; loc.append((i,hex(wb),hex(wa),None,None))
        if res==0:
            exact+=1; exact_b+=A[2][k][1]
        else:
            diffn+=1; per_fn_res[k]=res
        if want_fn:
            for l in loc: print('   @%-5d rebuilt=%-12s shipped=%-12s  %s -> %s'%l)
    print(f"shipped: {nfun} functions / {total} bytes of code")
    print(f"same-size functions:            {sized}")
    print(f"SEMANTICALLY IDENTICAL:         {exact} functions "
          f"({100*exact/nfun:.1f}% of all), {exact_b} bytes ({100*exact_b/total:.1f}% of .text)")
    print(f"same size but differing:        {diffn}")
    t=sum(kinds.values()) or 1
    for kk,v in kinds.most_common(): print(f"  {v:>7} ({100*v/t:>5.1f}%)  {kk}")
    print(f"\ntop offset corrections  (rebuilt -> shipped)   [delta]  count  example fn")
    for (mine,orig),c in pairs.most_common(npairs):
        ex=sorted(pairfns[(mine,orig)])[0]
        print(f"  {mine:>6} -> {orig:>6}   [{orig-mine:+6}]  {c:>5}  {ex}")
    print(f"\nfunctions with exactly 1 differing word: {sum(1 for v in per_fn_res.values() if v==1)}")
main()
