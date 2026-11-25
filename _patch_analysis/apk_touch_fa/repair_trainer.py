"""Repair stale SHV direct-call/benchmark offsets against this exact trainer ELF."""
from pathlib import Path
import struct,hashlib,json
ROOT=Path(__file__).resolve().parent
source=ROOT/'original-libshv.so';b=bytearray(source.read_bytes())
symbols={line.split(' ',2)[2]:int(line.split()[0],16) for line in (ROOT/'trainer-symbols.txt').read_text('utf-8').splitlines() if ' t ' in line and len(line.split(' ',2))==3}
phoff=struct.unpack_from('<Q',b,32)[0];phsize,phnum=struct.unpack_from('<HH',b,54);loads=[]
for i in range(phnum):
    typ,flags,off,va,pad,size,mem,align=struct.unpack_from('<II6Q',b,phoff+i*phsize)
    if typ==1:loads.append((off,va,size))
def offset(va):
    return next(off+va-start for off,start,size in loads if start<=va<start+size)
changes=[]
def mov_pair(lo_pc,hi_pc,old,new,reason):
    lo_off=offset(lo_pc);hi_off=offset(hi_pc);lo,hi=struct.unpack_from('<I',b,lo_off)[0],struct.unpack_from('<I',b,hi_off)[0]
    assert lo&0x7f800000==0x52800000 and hi&0x7f800000==0x72800000
    assert (lo&31)==(hi&31) and ((hi>>21)&3)==1
    assert ((lo>>5)&65535)|(((hi>>5)&65535)<<16)==old,(hex(lo_pc),hex(old))
    mask=0xffff<<5
    struct.pack_into('<I',b,lo_off,(lo&~mask)|((new&65535)<<5))
    struct.pack_into('<I',b,hi_off,(hi&~mask)|(((new>>16)&65535)<<5))
    changes.append({'low_instruction':hex(lo_pc),'high_instruction':hex(hi_pc),'before':hex(old),'after':hex(new),'reason':reason})
for lo,hi,old,name in [
    (0x1dc3c,0x1dc48,0x16c566c,'ped_commands::CommandKnockPedOffVehicle(int)'),
    (0x1dd04,0x1dd10,0x1763624,'task_commands::CommandTaskLeaveAnyVehicle(int, int, int)'),
    (0x1ddd8,0x1dde4,0x175b5c4,'task_commands::CommandTaskLeaveVehicle(int, int, int)'),
    (0x1df20,0x1df2c,0x17865b8,'vehicle_commands::CommandDeleteVehicle(int&)'),
    (0x1df94,0x1dfa0,0x176e148,'task_commands::CommandClearPedTasksImmediately(int)'),
    (0x1e0ac,0x1e0b8,0x18be9b4,'EndUserBenchmarks::OutputBenchmarkResults()')]:
    mov_pair(lo,hi,old,symbols[name],name)
benchmark=symbols['EndUserBenchmarks::OutputBenchmarkResults()']
engine=(ROOT/'trainer-original-libgtav.so').read_bytes()
# Verify these are the actual stream-result checks in the current function.
# The ELF text mapping has the same file/virtual delta at these addresses.
ep=struct.unpack_from('<Q',engine,32)[0];es,en=struct.unpack_from('<HH',engine,54)
def engine_word(va):
    for i in range(en):
        typ,flags,off,start,pad,size,mem,align=struct.unpack_from('<II6Q',engine,ep+i*es)
        if typ==1 and start<=va<start+size:return struct.unpack_from('<I',engine,off+va-start)[0]
    raise ValueError('Engine address absent')
for delta in (0xa4,0x74c):assert engine_word(benchmark+delta)==0xb100041f
mov_pair(0x1da94,0x1daa0,0x18bea58,benchmark+0xa4,'Benchmark checks follow current function layout')
mov_pair(0x1db08,0x1db14,0xb4002ec0,0xf100001f,'Compare stream pointer to NULL, retain existing conditional branch')
mov_pair(0x1db0c,0x1db18,0xb4fffc80,0xf100001f,'Compare frame-times stream pointer to NULL')
assert struct.unpack_from('<Q',b,0x25398)[0]==0x15fd570
new=symbols['misc_commands::CommandSaveEndUserBenchmarks()']
struct.pack_into('<Q',b,0x25398,new)
changes.append({'data_offset':'0x25398','before':'0x15fd570','after':hex(new),'reason':'No-argument benchmark save command fallback'})
target=ROOT/'repaired-libshv.so';target.write_bytes(b)
report={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'repaired_sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'engine_modified':False,'patches':changes,'status':'BUILT_REQUIRES_DEVICE_TEST'}
(ROOT/'trainer-native-repair.json').write_text(json.dumps(report,indent=2),'utf-8')
print('Trainer repair:',len(changes),'precise patches; game engine preserved.')
