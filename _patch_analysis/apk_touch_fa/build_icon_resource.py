from pathlib import Path
import zipfile,subprocess,os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
import arabic_reshaper
from bidi.algorithm import get_display
ROOT=Path(__file__).resolve().parent
WORK=ROOT/'icon-resource';RES=WORK/'res/drawable';RES.mkdir(parents=True,exist_ok=True)
f=TTFont(os.environ.get('FA_ICON_FONT',str(ROOT.parent.parent/'assets/Vazirmatn-Bold.ttf')));cm=f.getBestCmap();gs=f.getGlyphSet()
text=get_display(arabic_reshaper.reshape('فارسی'))
glyphs=[cm[ord(c)] for c in text];advance=sum(f['hmtx'][g][0] for g in glyphs)
bounds=[]
for g in glyphs:
    p=BoundsPen(gs);gs[g].draw(p)
    if p.bounds:bounds.append(p.bounds)
low=min(b[1] for b in bounds);high=max(b[3] for b in bounds)
scale=min(158/advance,48/(high-low));x=236-advance*scale/2;y=415+(high+low)*scale/2;paths=[]
for g in glyphs:
    pen=SVGPathPen(gs);gs[g].draw(TransformPen(pen,(scale,0,0,-scale,x,y)));paths.append(pen.getCommands());x+=f['hmtx'][g][0]*scale
path=' '.join(paths)
xml='''<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
<item><bitmap android:src="@*com.thegwchr.fuzzy.bootstrap:mipmap/ic_launcher_foreground" android:gravity="fill" /></item>
<item><vector android:width="573dp" android:height="601dp" android:viewportWidth="573" android:viewportHeight="601">
<path android:fillColor="#FF101010" android:strokeColor="#FFFFFFFF" android:strokeWidth="2.5" android:pathData="M157,382 H315 Q327,382 327,394 V436 Q327,448 315,448 H157 Q145,448 145,436 V394 Q145,382 157,382 Z" />
<path android:fillColor="#FFFFFFFF" android:pathData="PATH" />
</vector></item></layer-list>'''.replace('PATH',path)
(RES/'fa_launcher.xml').write_text(xml,'utf-8')
manifest='<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="dev.mobeegame.iconbuild"><uses-sdk android:minSdkVersion="30" android:targetSdkVersion="35"/><application/></manifest>'
(WORK/'AndroidManifest.xml').write_text(manifest,'utf-8')
aapt=r'D:\Sdk\build-tools\34.0.0\aapt2.exe'
subprocess.run([aapt,'compile',str(RES/'fa_launcher.xml'),'-o',str(WORK/'compiled.zip')],check=True)
subprocess.run([aapt,'link','-I',r'D:\Sdk\platforms\android-36\android.jar','-I',str(ROOT.parent.parent/'game_android_final.apk'),'--manifest',str(WORK/'AndroidManifest.xml'),'-o',str(WORK/'linked.apk'),str(WORK/'compiled.zip')],check=True)
with zipfile.ZipFile(WORK/'linked.apk') as z:
    names=[n for n in z.namelist() if n.startswith('res/') and n.endswith('.xml')]
    assert len(names)==1,names
    (ROOT/'fa-launcher.xml.bin').write_bytes(z.read(names[0]))
print('Native drawable created: original bitmap plus Persian vector text in jet-ski panel.')
