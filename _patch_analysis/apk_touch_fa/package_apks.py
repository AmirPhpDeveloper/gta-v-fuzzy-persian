from pathlib import Path
import subprocess, zipfile, json, hashlib, os, secrets
from branding import manifest_label,replace_strings
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
OUT=PROJECT/'Persian-Complete';OUT.mkdir(exist_ok=True)
SIGN=ROOT/'signing';SIGN.mkdir(exist_ok=True)
secret=SIGN/'store-password.txt'
if not secret.exists():secret.write_text(secrets.token_urlsafe(32),'ascii')
env=os.environ.copy();env['FUZZY_FA_STOREPASS']=secret.read_text('ascii')
key=SIGN/'fuzzy-persian.jks'
if not key.exists():
    subprocess.run([r'C:\Program Files\Java\jdk-17\bin\keytool.exe','-genkeypair','-keystore',str(key),'-storepass:env','FUZZY_FA_STOREPASS','-keypass:env','FUZZY_FA_STOREPASS','-alias','fuzzy-persian','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Fuzzy Persian Localization, O=Persian Localization, C=IR'],env=env,check=True)
reports={}
for variant,source in [('normal','game_android_final.apk'),('trainer','game_android_final_signed by mohd saib.apk')]:
    original=PROJECT/source
    built=ROOT/(variant+'-built.apk')
    additions={'classes.dex':zipfile.ZipFile(built).read('classes.dex'),'classes2.dex':(ROOT/'helper-dex/classes.dex').read_bytes(),'assets/hud/fa_gamesub.ttf':(ROOT/'fa_gamesub.ttf').read_bytes()}
    changed={'classes.dex'}
    if variant=='trainer':
        additions['lib/arm64-v8a/libshv.so']=(ROOT/'repaired-libshv.so').read_bytes()
        changed.add('lib/arm64-v8a/libshv.so')
    with zipfile.ZipFile(original) as original_zip:
        label='Grand Theft Auto V'+(' Trainer' if variant=='trainer' else '')+' fa'
        additions['AndroidManifest.xml']=manifest_label(original_zip.read('AndroidManifest.xml'),label)
        changed.add('AndroidManifest.xml')
        icon_paths=[n for n in original_zip.namelist() if n.startswith('res/mipmap-') and n.endswith('/ic_launcher.png')]
        replacements={n:n.removesuffix('.png')+'.xml' for n in icon_paths}
        additions['resources.arsc']=replace_strings(original_zip.read('resources.arsc'),replacements);changed.add('resources.arsc')
        for name in icon_paths:
            foreground=name.replace('/ic_launcher.png','/ic_launcher_foreground.png')
            additions[foreground]=original_zip.read(name);changed.add(foreground)
            additions[replacements[name]]=(ROOT/'fa-launcher.xml.bin').read_bytes()
    if variant=='normal':
        additions['assets/touch/atlas.bin']=(ROOT/'fa-touch-atlas.bin').read_bytes()
        additions['lib/arm64-v8a/libfuzzyfa.so']=(ROOT/'normal-libfuzzyfa.so').read_bytes()
        changed.add('assets/touch/atlas.bin')
    unsigned=ROOT/(variant+'-unsigned.apk');aligned=ROOT/(variant+'-aligned.apk')
    with zipfile.ZipFile(original) as old,zipfile.ZipFile(unsigned,'w',allowZip64=False) as new:
        for info in old.infolist():
            upper=info.filename.upper()
            if upper.startswith('META-INF/') and (upper.endswith(('.SF','.RSA','.DSA','.EC')) or upper=='META-INF/MANIFEST.MF'):continue
            new.writestr(info,additions.pop(info.filename,old.read(info.filename)))
        for name,data in additions.items():new.writestr(name,data,compress_type=zipfile.ZIP_STORED)
    subprocess.run([r'D:\Sdk\build-tools\34.0.0\zipalign.exe','-f','-p','4',str(unsigned),str(aligned)],check=True)
    output=OUT/('Fuzzy-'+('Normal' if variant=='normal' else 'Trainer')+'-fa.apk')
    subprocess.run([r'D:\Sdk\build-tools\34.0.0\apksigner.bat','sign','--ks',str(key),'--ks-key-alias','fuzzy-persian','--ks-pass','env:FUZZY_FA_STOREPASS','--key-pass','env:FUZZY_FA_STOREPASS','--out',str(output),str(aligned)],env=env,check=True)
    verify=subprocess.run([r'D:\Sdk\build-tools\34.0.0\apksigner.bat','verify','--verbose','--print-certs',str(output)],capture_output=True,text=True,check=True)
    (ROOT/(variant+'-signature.txt')).write_text(verify.stdout,'utf-8')
    subprocess.run([r'D:\Sdk\build-tools\34.0.0\zipalign.exe','-c','-p','4',str(output)],check=True)
    unchanged=[]
    with zipfile.ZipFile(original) as old,zipfile.ZipFile(output) as new:
        assert new.testzip() is None
        for name in old.namelist():
            if name in changed or name.upper().startswith('META-INF/'):continue
            assert old.read(name)==new.read(name),name
            unchanged.append(name)
        assert new.read('classes2.dex')==(ROOT/'helper-dex/classes.dex').read_bytes()
        assert new.read('assets/hud/fa_gamesub.ttf')==(ROOT/'fa_gamesub.ttf').read_bytes()
        libs={n:hashlib.sha256(new.read(n)).hexdigest() for n in new.namelist() if n.endswith('.so')}
    reports[variant]={'file':str(output),'size':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'unchanged_original_entries':len(unchanged),'original_native_libraries':libs,'signature_verified':True,'aligned':True}
(OUT/'apk-verification.json').write_text(json.dumps(reports,indent=2),'utf-8')
print(json.dumps({k:{'size':v['size'],'sha256':v['sha256']} for k,v in reports.items()},indent=2))
