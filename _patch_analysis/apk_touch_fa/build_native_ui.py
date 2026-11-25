from pathlib import Path
import json,struct,subprocess,zipfile,re,math
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
import arabic_reshaper
from bidi.algorithm import get_display
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent
NDK=Path(r'D:\Sdk\ndk\26.1.10909125\toolchains\llvm\prebuilt\windows-x86_64\bin')

def atlas():
    f=ImageFont.truetype(str(ROOT/'fa_gamesub.ttf'),64)
    cmap=TTFont(ROOT/'fa_gamesub.ttf').getBestCmap()
    cps=sorted(cp for cp in cmap if cp>=32 and cp not in range(0x2000,0x2070))
    image=Image.new('L',(2048,2048));draw=ImageDraw.Draw(image)
    records=[];x=y=2;rowheight=0
    for cp in cps:
        ch=chr(cp);l,t,r,b=f.getbbox(ch,anchor='ls');w,h=r-l,b-t
        if x+w+2>image.width:x=2;y+=rowheight+2;rowheight=0
        assert y+h+2<=image.height,(cp,y,h)
        if w and h:draw.text((x-l,y-t),ch,font=f,fill=255,anchor='ls')
        advance=round(f.getlength(ch)*64)
        records.append(struct.pack('<IHHHHhhH',cp,x,y,w,h,l,t,advance))
        x+=w+2;rowheight=max(rowheight,h)
    height=y+rowheight+2;image=image.crop((0,0,2048,height))
    asc,desc=f.getmetrics()
    data=struct.pack('<4sI6H',b'HUDF',1,2048,height,64,asc,desc,len(records))+b''.join(records)+image.tobytes()
    (ROOT/'fa-font.bin').write_bytes(data)
    image.save(ROOT/'native-font-atlas.png')
    assert len(data)==20+18*len(records)+2048*height
    print('Native atlas:',len(records),'glyphs',len(data),'bytes')

def touch_atlas():
    old=(ROOT/'original-touch-atlas.bin').read_bytes()
    magic,version,width,height,icons,glyphs=struct.unpack_from('<4sI4H',old)
    assert (magic,version,width,height,icons,glyphs)==(b'TATC',3,2048,2816,85,1875)
    table=1872;pixels=table+glyphs*40
    assert len(old)-pixels==width*height*4
    image=Image.frombytes('RGBA',(width,height),old[pixels:])
    # All original icon and pill texels are above row 1032.
    assert min(struct.unpack_from('<I9f',old,table+i*40)[2] for i in range(glyphs))>=1034
    image.paste((0,0,0,0),(0,1032,width,height))
    f=ImageFont.truetype(str(ROOT/'fa_gamesub.ttf'),40);cmap=TTFont(ROOT/'fa_gamesub.ttf').getBestCmap()
    cps=sorted(cp for cp in cmap if cp>=32 and cp not in range(0x2000,0x2070))
    records=[];x=2;y=1034;row=0;draw=ImageDraw.Draw(image)
    for cp in cps:
        ch=chr(cp);l,t,r,b=f.getbbox(ch,anchor='ls');w,h=r-l,b-t
        if x+max(1,w)+2>width:x=2;y+=row+2;row=0
        assert y+max(1,h)+2<=height
        if w and h:draw.text((x-l,y-t),ch,font=f,fill=(255,255,255,255),anchor='ls')
        records.append(struct.pack('<I9f',cp,x,y,x+max(1,w),y+max(1,h),w,h,l,t,f.getlength(ch)))
        x+=max(1,w)+2;row=max(row,max(1,h))
    header=bytearray(old[:table]);struct.pack_into('<H',header,14,len(records))
    asc,desc=f.getmetrics();struct.pack_into('<3f',header,160,asc,desc,40)
    result=bytes(header)+b''.join(records)+image.tobytes()
    (ROOT/'fa-touch-atlas.bin').write_bytes(result)
    # Icon geometry and every original icon pixel remain unchanged.
    assert header[:14]==old[:14] and header[172:table]==old[172:table]
    assert image.crop((0,0,width,1032)).tobytes()==Image.frombytes('RGBA',(width,height),old[pixels:]).crop((0,0,width,1032)).tobytes()
    print('Touch atlas:',len(records),'glyphs; original icons preserved')

def symbols_and_calls(variant):
    apk=PROJECT/('game_android_final.apk' if variant=='normal' else 'game_android_final_signed by mohd saib.apk')
    dest=ROOT/(variant+'-original-libgtav.so')
    with zipfile.ZipFile(apk) as z:dest.write_bytes(z.read('lib/arm64-v8a/libgtav.so'))
    nm=subprocess.check_output([str(NDK/'llvm-nm.exe'),'-n','-C',str(dest)],text=True)
    targets={}
    for line in nm.splitlines():
        for short in ('TouchMeasureText','TouchEmitText'):
            if short+'(' in line:targets[short]=int(line.split()[0],16)
    assert len(targets)==2
    b=dest.read_bytes();phoff=struct.unpack_from('<Q',b,32)[0];phsize,phnum=struct.unpack_from('<HH',b,54)
    loads=[]
    for i in range(phnum):
        typ,flags,offset,vaddr,paddr,filesz,memsz,align=struct.unpack_from('<II6Q',b,phoff+i*phsize)
        if typ==1 and flags&1:loads.append((offset,vaddr,filesz))
    calls=[]
    for off,addr,size in loads:
        for j in range(0,size-3,4):
            ins=struct.unpack_from('<I',b,off+j)[0]
            if ins&0xfc000000 not in (0x94000000,0x14000000):continue
            imm=ins&0x3ffffff
            if imm&0x2000000:imm-=0x4000000
            dst=addr+j+imm*4
            for kind,target in enumerate(targets.values()):
                if dst==target:calls.append((addr+j,ins,kind))
    assert len(calls)>2,(variant,calls)
    print(variant,targets,'calls',len(calls))
    return targets,calls

def native(variant):
    targets,calls=symbols_and_calls(variant)
    mapping=json.loads((ROOT/'translation-map.json').read_text('utf-8'))
    # Native HUD consumes individual glyphs, so use shaped visual-order strings.
    rows=[]
    for k,v in mapping.items():
        if any(0x600<=ord(c)<=0x6ff for c in v):v=get_display(arabic_reshaper.reshape(v))
        rows.append('{'+json.dumps(k,ensure_ascii=True)+','+json.dumps(v,ensure_ascii=True)+'},')
    source=r'''#include <jni.h>
#include <link.h>
#include <sys/mman.h>
#include <unistd.h>
#include <android/log.h>
#include <cstring>
#include <cstdint>
#include <string>
#include <atomic>
#include <cerrno>
struct Entry {const char* key;const char* value;};
static Entry entries[]={ENTRIES};
struct Call {uintptr_t offset;uint32_t original;int kind;};
static Call calls[]={CALLS};
static uintptr_t base=0;
static std::string key(const char* s,const char* end){std::string out;for(;s<end&&*s;s++){unsigned char c=*s;if(c>='A'&&c<='Z')out.push_back(c+32);else if((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='%'||c=='$')out.push_back(c);else if(c>=128)return std::string();}return out;}
static const char* translate(const char* begin,const char* end){if(!begin||end<begin||end-begin>4096)return nullptr;std::string k=key(begin,end);if(k.empty())return nullptr;for(const auto& e:entries)if(k==e.key)return e.value;return nullptr;}
using Measure=float(*)(const char*,const char*,float);
using Emit=void(*)(void*,const char*,const char*,float,float,float,uint32_t,bool,float);
static Measure originalMeasure;
static Emit originalEmit;
extern "C" { __attribute__((visibility("hidden"))) uintptr_t gMeasureResume=0,gEmitResume=0; }
extern "C" __attribute__((naked)) float resumeMeasure(const char*,const char*,float){__asm__ volatile("fmov s1, s0\n movi d0, #0\n cbz x0, 1f\n cmp x0, x1\n adrp x17, gMeasureResume\n ldr x17, [x17, :lo12:gMeasureResume]\n br x17\n 1: ret\n");}
extern "C" __attribute__((naked)) void resumeEmit(void*,const char*,const char*,float,float,float,uint32_t,bool,float){__asm__ volatile("stp d11, d10, [sp, #-0x50]!\n stp d9, d8, [sp, #0x10]\n str x30, [sp, #0x20]\n stp x22, x21, [sp, #0x30]\n adrp x17, gEmitResume\n ldr x17, [x17, :lo12:gEmitResume]\n br x17\n");}
extern "C" float faMeasure(const char* begin,const char* end,float size){static int seen=0;if(seen++<3)__android_log_print(4,"FuzzyFaNative","Measure %.*s",static_cast<int>(end-begin),begin);if(const char* t=translate(begin,end)){begin=t;end=t+strlen(t);}return originalMeasure(begin,end,size);}
extern "C" void faEmit(void* batch,const char* begin,const char* end,float x,float y,float size,uint32_t color,bool centered,float extra){static int seen=0;if(seen++<3)__android_log_print(4,"FuzzyFaNative","Emit %.*s",static_cast<int>(end-begin),begin);if(const char* t=translate(begin,end)){begin=t;end=t+strlen(t);}originalEmit(batch,begin,end,x,y,size,color,centered,extra);}
static int find(struct dl_phdr_info* info,size_t,void*){const char* n=strrchr(info->dlpi_name,'/');if(strcmp(n?n+1:info->dlpi_name,"libgtav.so")==0){base=info->dlpi_addr;return 1;}return 0;}
static bool install(){dl_iterate_phdr(find,nullptr);if(!base){__android_log_print(6,"FuzzyFaNative","Engine not found");return false;}
  const uint32_t expectedMeasure[]={0x1e204001,0x2f00e400,0xb40014e0,0xeb01001f};
  const uint32_t expectedEmit[]={0x6dbb2beb,0x6d0123e9,0xf90013fe,0xa90357f6};
  if(memcmp(reinterpret_cast<void*>(base+MEASURE),expectedMeasure,16)||memcmp(reinterpret_cast<void*>(base+EMIT),expectedEmit,16)){__android_log_print(6,"FuzzyFaNative","Unexpected text function prologue");return false;}
  gMeasureResume=base+MEASURE+16;gEmitResume=base+EMIT+16;
  originalMeasure=resumeMeasure;originalEmit=resumeEmit;
  size_t pagesize=static_cast<size_t>(sysconf(_SC_PAGESIZE));
  uintptr_t funcs[]={base+MEASURE,base+EMIT};uintptr_t wrappers[]={reinterpret_cast<uintptr_t>(faMeasure),reinterpret_cast<uintptr_t>(faEmit)};
  for(int i=0;i<2;i++){uintptr_t textpage=funcs[i]&~(pagesize-1);if(mprotect(reinterpret_cast<void*>(textpage),pagesize,PROT_READ|PROT_WRITE|PROT_EXEC)!=0)return false;
    uint32_t code[4]={0x58000050,0xd61f0200,0,0};memcpy(code+2,&wrappers[i],8);memcpy(reinterpret_cast<void*>(funcs[i]),code,16);
    __builtin___clear_cache(reinterpret_cast<char*>(funcs[i]),reinterpret_cast<char*>(funcs[i]+16));mprotect(reinterpret_cast<void*>(textpage),pagesize,PROT_READ|PROT_EXEC);
  }return true;
}
/* Retained diagnostic implementation; not used for installation. */
static bool installCalls(){dl_iterate_phdr(find,nullptr);if(!base)return false;
  for(const auto& c:calls)if(*reinterpret_cast<uint32_t*>(base+c.offset)!=c.original){__android_log_print(6,"FuzzyFaNative","Unexpected instruction at %lx: %x vs %x",c.offset,*reinterpret_cast<uint32_t*>(base+c.offset),c.original);return false;}
  size_t pagesize=static_cast<size_t>(sysconf(_SC_PAGESIZE));void* page=MAP_FAILED;
  for(intptr_t distance=-0x7800000;distance<0x7800000;distance+=0x10000){
    uintptr_t hint=(base+MEASURE+distance)&~(pagesize-1);
    page=mmap(reinterpret_cast<void*>(hint),pagesize,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|0x100000,-1,0);
    if(page!=MAP_FAILED)break;
  }
  if(page==MAP_FAILED){__android_log_print(6,"FuzzyFaNative","No nearby code page: %d",errno);return false;}
  uintptr_t wrappers[]={reinterpret_cast<uintptr_t>(faMeasure),reinterpret_cast<uintptr_t>(faEmit)};
  for(int i=0;i<2;i++){uint32_t* code=reinterpret_cast<uint32_t*>(static_cast<char*>(page)+16*i);code[0]=0x58000050;code[1]=0xd61f0200;memcpy(code+2,&wrappers[i],8);}
  __builtin___clear_cache(static_cast<char*>(page),static_cast<char*>(page)+32);
  if(mprotect(page,pagesize,PROT_READ|PROT_EXEC)!=0){__android_log_print(6,"FuzzyFaNative","Code protection failed: %d",errno);munmap(page,pagesize);return false;}
  originalMeasure=reinterpret_cast<Measure>(base+MEASURE);originalEmit=reinterpret_cast<Emit>(base+EMIT);
  for(const auto& c:calls){uintptr_t pc=base+c.offset;uintptr_t dest=reinterpret_cast<uintptr_t>(page)+16*c.kind;intptr_t displacement=static_cast<intptr_t>(dest-pc);
    if(displacement<-(1LL<<27)||displacement>=(1LL<<27)){__android_log_print(6,"FuzzyFaNative","Code page out of branch range");return false;}
    uintptr_t textpage=pc&~(pagesize-1);if(mprotect(reinterpret_cast<void*>(textpage),pagesize,PROT_READ|PROT_WRITE|PROT_EXEC)!=0){__android_log_print(6,"FuzzyFaNative","Text protection failed: %d",errno);return false;}
    uint32_t replacement=(c.original&0xfc000000)|(static_cast<uint32_t>(displacement/4)&0x03ffffff);
    __atomic_store_n(reinterpret_cast<uint32_t*>(pc),replacement,__ATOMIC_RELEASE);
    __builtin___clear_cache(reinterpret_cast<char*>(pc),reinterpret_cast<char*>(pc+4));
    mprotect(reinterpret_cast<void*>(textpage),pagesize,PROT_READ|PROT_EXEC);
  }return true;
}
extern "C" JNIEXPORT jint JNI_OnLoad(JavaVM*,void*){bool ok=install();__android_log_print(ok?ANDROID_LOG_INFO:ANDROID_LOG_ERROR,"FuzzyFaNative",ok?"Native caption translation ready":"Native caption translation unavailable");return JNI_VERSION_1_6;}
'''.replace('ENTRIES','\n'.join(rows)).replace('CALLS',','.join('{%d,%d,%d}'%c for c in calls)).replace('MEASURE',str(targets['TouchMeasureText'])).replace('EMIT',str(targets['TouchEmitText']))
    cpp=ROOT/(variant+'-native.cpp');cpp.write_text(source,'utf-8')
    output=ROOT/(variant+'-libfuzzyfa.so')
    subprocess.run([str(NDK/'aarch64-linux-android30-clang++.cmd'),'-std=c++17','-O2','-shared','-fPIC','-static-libstdc++','-fvisibility=hidden','-Wl,-z,max-page-size=16384',str(cpp),'-llog','-ldl','-o',str(output)],check=True)
    (ROOT/(variant+'-native-calls.json')).write_text(json.dumps({'targets':targets,'calls':calls},indent=2),'utf-8')

if __name__=='__main__':
    atlas()
    touch_atlas()
    native('normal')
    # Trainer uses the Java TouchOverlay; normal uses the Vulkan HUD path.
    path=ROOT/'normal/smali/com/thegwchr/fuzzy/GTAVNativeActivity.smali'
    s=path.read_text('utf-8')
    hook='    invoke-static {}, Lcom/thegwchr/fuzzy/FaTouchUi;->nativeReady()V'
    if hook not in s:
        anchor='    invoke-super {p0, p1}, Landroid/app/NativeActivity;->onCreate(Landroid/os/Bundle;)V'
        assert s.count(anchor)==1
        s=s.replace(anchor,anchor+'\n\n'+hook);path.write_text(s,'utf-8')
