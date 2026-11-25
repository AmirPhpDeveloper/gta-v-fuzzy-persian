from pathlib import Path
import zipfile,json,hashlib,struct,math,sys
ROOT=Path(__file__).resolve().parent;A=ROOT.parent;PROJECT=A.parent
PUBLIC=PROJECT/'github-release';OUT=PROJECT/'Persian-Complete/releases';OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(A));from rpf_index import read_index
BLOCK=4*1024*1024
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def prefix(p):
    with p.open('rb') as f:magic,count,names,flags=struct.unpack('<4I',f.read(16))
    assert magic==0x52504637
    return math.ceil((16+16*count+names)/512)*512
def entry(p,name):return next(e for e in read_index(p)['entries'] if e.get('path')==name)
def item(relative,source,target):return {'path':relative,'source_bytes':source.stat().st_size,'source_sha256':sha(source),'target_bytes':target.stat().st_size,'target_sha256':sha(target),'copies':[{'source_offset':0,'offset':0,'bytes':source.stat().st_size}],'parts':[]}
def part(z,obj,target,offset,count,name):
    h=hashlib.sha256();remaining=count
    with target.open('rb') as inp,z.open(name,'w',force_zip64=True) as out:
        inp.seek(offset)
        while remaining:
            block=inp.read(min(BLOCK,remaining));assert block
            out.write(block);h.update(block);remaining-=len(block)
    obj['parts'].append({'archive':Path(z.filename).name,'entry':name,'offset':offset,'bytes':count,'sha256':h.hexdigest()})
def manifest(component,files):
    d={'format':'fuzzy-range-patch-v1','component':component,'base_build':'Fuzzy Android 1.61.1 supplied data','files':files}
    p=PUBLIC/'manifests'/f'{component}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2),'utf-8')
    return p
def localization():
    target=A/'full_patch_v6/patch_root/com.thegwchr.fuzzy/files/game/update';source=A/'base';files=[]
    archive=OUT/'Fuzzy-Localization-data.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in ('update.rpf','update2.rpf'):
            src=source/name;dst=target/name;obj=item('update/'+name,src,dst)
            part(z,obj,dst,0,prefix(dst),'payload/'+name+'.header')
            if name=='update.rpf':
                path='android/data/cdimages/scaleform_platform_pc.rpf';old=entry(src,path);new=entry(dst,path)
                start=new['file_offset_sector']*512;old_size=old['uncompressed_size']
                obj['copies'].append({'source_offset':old['file_offset_sector']*512,'offset':start,'bytes':old_size})
                platform=A/'diagnostic/fixed-scaleform_platform_pc.rpf'
                part(z,obj,dst,start,prefix(platform),'payload/platform.header')
                part(z,obj,dst,start+old_size,new['uncompressed_size']-old_size,'payload/platform.font')
                fontmap=entry(dst,'common/data/ui/fontmap.xml')
                part(z,obj,dst,fontmap['file_offset_sector']*512,fontmap['uncompressed_size'],'payload/fontmap.xml')
            else:
                part(z,obj,dst,src.stat().st_size,dst.stat().st_size-src.stat().st_size,'payload/language.rpf')
            files.append(obj)
    manifest('localization',files)
    print('Localization download:',archive.stat().st_size,flush=True)
def dubbing():
    target=A/'full_patch_v6/patch_root/com.thegwchr.fuzzy/files/game/android/audio/sfx';files=[];archives=[];z=None;raw=0
    try:
        for dst in sorted(target.glob('*.rpf')):
            src=A/'android_dub_work/base_rpf'/dst.name
            if not src.exists():src=A/'android_dub_work/base_rpf_open'/dst.name
            tail=dst.stat().st_size-src.stat().st_size
            if z is None or (raw+tail>850_000_000 and raw):
                if z:z.close()
                archives.append(OUT/f'Fuzzy-Dubbing-data-{len(archives)+1:02}.zip')
                z=zipfile.ZipFile(archives[-1],'w',zipfile.ZIP_DEFLATED,compresslevel=9);raw=0
            obj=item('android/audio/sfx/'+dst.name,src,dst)
            part(z,obj,dst,0,prefix(dst),'payload/'+dst.name+'.header')
            part(z,obj,dst,src.stat().st_size,tail,'payload/'+dst.name+'.tail')
            raw+=tail;files.append(obj);print('Packed dubbing:',dst.name,flush=True)
    finally:
        if z:z.close()
    assert len(files)==29
    manifest('dubbing',files)
    print('Dubbing download:',sum(p.stat().st_size for p in archives),flush=True)
if __name__=='__main__':
    localization();dubbing()
    report={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.glob('*.zip')}
    (ROOT/'compact-report.json').write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report,indent=2),flush=True)
