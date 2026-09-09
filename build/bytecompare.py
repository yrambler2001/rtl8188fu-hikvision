#!/usr/bin/env python3
"""Byte-level comparison of a rebuilt 8188fu.ko against the shipped one.

Masks two things that are layout, not code:
  * relocated operands (resolved at link time)
  * ARM B/BL displacements that the assembler resolved inside .text
usage: build/bytecompare.py <original.ko> [rebuilt.ko]
"""
import subprocess, re, struct, sys, collections

READELF = 'arm-none-eabi-readelf'

def sections(f):
    out = subprocess.run([READELF,'-SW',f],capture_output=True,text=True).stdout
    return {int(m.group(1)):{'name':m.group(2),'off':int(m.group(4),16)} for m in
            re.finditer(r'\[\s*(\d+)\]\s+(\S+)\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)\s+([0-9a-f]+)',out)}

def symbols(f):
    out = subprocess.run([READELF,'-sW',f],capture_output=True,text=True).stdout
    d={}
    for line in out.splitlines():
        p=line.split()
        if len(p)>=8 and p[3]=='FUNC' and p[6].isdigit():
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

def body(L,name):
    data,secs,syms,rels = L
    val,size,ndx = syms[name]
    if ndx not in secs or size==0: return None
    off=secs[ndx]['off']+val
    b=bytearray(data[off:off+size])
    for r in rels.get(ndx,()):
        if val<=r<val+size: b[r-val:r-val+4]=b'\0\0\0\0'
    for i in range(0,size-3,4):
        w=struct.unpack_from('<I',b,i)[0]
        if (w>>25)&0x7==0b101: struct.pack_into('<I',b,i,w&0xFF000000)
    return bytes(b)

def main():
    A=load(sys.argv[1]); B=load(sys.argv[2] if len(sys.argv)>2 else './8188fu.ko')
    total=sum(s for _,s,_ in A[2].values())
    exact=exact_b=sized=0; kinds=collections.Counter(); ndiff=0
    for k in A[2]:
        if k not in B[2] or A[2][k][1]!=B[2][k][1] or A[2][k][1]==0: continue
        sized+=1
        a,b=body(A,k),body(B,k)
        if a is None or b is None: continue
        if a==b:
            exact+=1; exact_b+=A[2][k][1]; continue
        ndiff+=1
        for i in range(0,min(len(a),len(b))-3,4):
            wa=struct.unpack_from('<I',a,i)[0]; wb=struct.unpack_from('<I',b,i)[0]
            if wa==wb: continue
            ldst=((wa>>26)&0x3)==0b01
            if ldst and (wa&0xFFFFF000)==(wb&0xFFFFF000):
                kinds['ldr/str immediate offset (struct layout / kernel headers)']+=1
            elif ldst: kinds['ldr/str, other field']+=1
            elif (wa&0x0FF00000)==(wb&0x0FF00000): kinds['same opcode, operand differs']+=1
            else: kinds['different opcode']+=1
    print(f"original: {len(A[2])} functions / {total} bytes of code")
    print(f"same-size functions:            {sized}")
    print(f"REPRODUCED EXACTLY:             {exact} functions "
          f"({100*exact/len(A[2]):.1f}% of all), {exact_b} bytes ({100*exact_b/total:.1f}% of .text)")
    print(f"\nsame size but differing:        {ndiff}")
    t=sum(kinds.values()) or 1
    for k,v in kinds.most_common(): print(f"  {v:>7} ({100*v/t:>5.1f}%)  {k}")

main()
