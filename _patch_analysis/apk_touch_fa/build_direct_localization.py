from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent.parent;OUT=PROJECT/'Persian-Complete/releases'
GAME=ROOT.parent/'full_patch_v6/patch_root/com.thegwchr.fuzzy/files/game'
RAR=r'C:\Program Files\WinRAR\Rar.exe';archive=OUT/'Fuzzy-Localization-fa.rar'
previous=OUT/'Fuzzy-Localization-Compact-fa.rar'
if archive.exists() and not previous.exists():archive.rename(previous)
inputs=[GAME/'update/update.rpf',GAME/'update/update2.rpf']
assert [p.stat().st_size for p in inputs]==[826202586,333024256]
subprocess.run([RAR,'a','-ma5','-m5','-md64m','-mt4','-hpmobeegame','-idq','-y',str(archive),'update/update.rpf','update/update2.rpf'],cwd=GAME,check=True)
subprocess.run([RAR,'t','-pmobeegame','-idq',str(archive)],check=True)
listing=subprocess.check_output([RAR,'lb','-pmobeegame',str(archive)],text=True).splitlines()
assert sorted(x.replace('\\','/') for x in listing)==['update/update.rpf','update/update2.rpf'],listing
assert archive.stat().st_size<2_000_000_000
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
report={'mode':'direct-replacement-no-python','archive':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'password':'mobeegame','rar_test':'PASS','contains_only_two_update_files':True,'files':[{'path':'update/'+p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in inputs]}
(ROOT/'direct-localization-distribution.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report,indent=2),flush=True)
