from pathlib import Path
import argparse,subprocess,shutil,os,json,hashlib,sys
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent;PUBLIC=PROJECT/'github-release';RELEASE=PROJECT/'Persian-Complete/releases';RAR=r'C:\Program Files\WinRAR\Rar.exe'
def link(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():os.link(source,target)
def build(component):
    if component=='localization':
        subprocess.run([sys.executable,str(ROOT/'build_direct_localization.py')],check=True)
        return
    stage=ROOT/'distribution-stage'/component;stage.mkdir(parents=True,exist_ok=True)
    for name in ['RUN-WINDOWS.cmd','README-INSTALL-FA.txt']:
        shutil.copy2(PUBLIC/name,stage/name)
    for folder in ('installer','manifests'):
        (stage/folder).mkdir(exist_ok=True)
        for file in (PUBLIC/folder).glob('*'):
            if file.is_file():shutil.copy2(file,stage/folder/file.name)
    if component=='dubbing':
        for file in RELEASE.glob('Fuzzy-Dubbing-data-*.zip'):link(file,stage/file.name)
        archive=RELEASE/'Fuzzy-Dubbing-fa.rar';volume=['-v1800m']
    else:
        link(RELEASE/'Fuzzy-Localization-data.zip',stage/'Fuzzy-Localization-data.zip')
        for file in (PROJECT/'Persian-Complete').glob('Fuzzy-*-fa.apk'):shutil.copy2(file,stage/file.name)
        archive=RELEASE/'Fuzzy-Localization-fa.rar';volume=[]
    subprocess.run([RAR,'a','-ma5','-m0','-hpmobeegame','-r','-ep1','-idq','-y',*volume,str(archive),'.'],cwd=stage,check=True)
    parts=sorted(RELEASE.glob('Fuzzy-Dubbing-fa.part*.rar')) if component=='dubbing' else [archive]
    assert parts and all(p.stat().st_size<2_000_000_000 for p in parts)
    subprocess.run([RAR,'t','-pmobeegame','-idq',str(parts[0])],check=True)
    report={}
    for p in parts:
        with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
        report[p.name]={'bytes':p.stat().st_size,'sha256':sha,'password':'mobeegame','rar_test':'PASS'}
    (ROOT/(component+'-distribution.json')).write_text(json.dumps(report,indent=2),'utf-8')
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('component',choices=['dubbing','localization']);build(parser.parse_args().component)
