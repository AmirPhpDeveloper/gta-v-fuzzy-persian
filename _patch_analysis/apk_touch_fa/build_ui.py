from pathlib import Path
import json, re, unicodedata, hashlib, zipfile, subprocess, os
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent.parent
PKG='Lcom/thegwchr/fuzzy/FaTouchUi;'
def tsv(name):
    return dict(line.split('\t',1) for line in (ROOT/name).read_text('utf-8-sig').splitlines() if line.strip())
def norm(s):
    return ''.join(c.lower() for c in s if c.isalnum() or c in '%$').strip()
def load_maps():
    en=json.loads((ROOT/'tr-english.json').read_text('utf-8-sig'))
    fa=tsv('ui-fa.tsv')
    assert en.keys()==fa.keys(), (en.keys()-fa.keys(),fa.keys()-en.keys())
    fmt=re.compile(r'%(?:\d+\$)?[-#+ 0,(]*\d*(?:\.\d+)?[a-zA-Z%]')
    result={}
    for key,source in en.items():
        target=fa[key].replace('\\n','\n')
        assert fmt.findall(source)==fmt.findall(target),(key,source,target)
        result[norm(source)]=target
    controls=tsv('controls-fa.tsv')
    result.update({norm(k):v for k,v in controls.items()})
    result.update({norm(k):v for k,v in tsv('extra-controls-fa.tsv').items()})
    result.update({norm(k):v for k,v in tsv('trainer-fa.tsv').items()})
    # Native captions are generated from enum names, independently of GXT.
    labels=json.loads((ROOT.parent/'diagnostic/touch-ui/input-labels.json').read_text('utf-8-sig'))
    for entry in labels:
        key=entry['key'].removeprefix('INPUT_').removeprefix('VEH_').replace('_',' ')
        target=result.get(norm(entry['english']))
        if target is None and entry['gamesub']!=entry['english']:
            target=entry['gamesub']
        if target:
            result[norm(key)]=target
            result[norm(entry['english'])]=target
    (ROOT/'translation-map.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    return result

def font(mapping):
    src=ROOT.parent/'diagnostic/touch-ui/unicode-fonts-final/9_$Font2_Chalet-LondonNineteenSixty.ttf'
    f=TTFont(src); cm=f.getBestCmap(); additions={}; forms={}
    # Supplement only marks and yeh-with-hamza absent in the GameSub glyph set.
    fallback=TTFont(ROOT/'fallback-arabic.ttf');fc=fallback.getBestCmap();gs=fallback.getGlyphSet()
    scale=f['head'].unitsPerEm/fallback['head'].unitsPerEm
    required={ord(c) for s in mapping.values() for c in s if ord(c)>127 and ord(c) not in cm}
    required.update((0xfe89,0xfe8a,0xfe8b,0xfe8c))
    for cp in sorted(required):
        if cp not in fc:continue
        name='faExtra%04X'%cp
        rec=DecomposingRecordingPen(gs);gs[fc[cp]].draw(rec)
        pen=TTGlyphPen(None);rec.replay(TransformPen(pen,(scale,0,0,scale,0,0)))
        f['glyf'][name]=pen.glyph()
        width,lsb=fallback['hmtx'][fc[cp]];f['hmtx'][name]=(round(width*scale),round(lsb*scale))
        f.setGlyphOrder(list(dict.fromkeys(f.getGlyphOrder()+[name])));additions[cp]=name
    if 0x25cf in required:
        additions[0x25cf]=cm.get(0x2022,cm[ord('*')])
    for table in f['cmap'].tables:
        if table.isUnicode():table.cmap.update(additions)
    cm=f.getBestCmap()
    for cp,glyph in list(cm.items()):
        dec=unicodedata.decomposition(chr(cp)).split()
        if len(dec)==2 and dec[0] in ('<isolated>','<initial>','<medial>','<final>'):
            base=int(dec[1],16)
            forms.setdefault(base,{})[dec[0][1:-1]]=glyph
    for cp,source in {0xfe81:0x4e72,0xfe80:0x4e71,0x060c:0x4e64,0x061f:0x4e70}.items():
        if source in cm: additions[cp]=cm[source]
    # These outlined glyphs are the exact GameSub Persian forms.
    for base,shapes in forms.items():
        additions[base]=shapes.get('isolated',next(iter(shapes.values())))
    additions[0x0622]=additions[0xfe81]
    forms[0x0622]={'isolated':additions[0xfe81],'final':cm[0xfe82]}
    for i,cp in enumerate([0x4f0b,0x4f53,0x4f54,0x4f84,0x4f85,0x4f86,0x4f87,0x4f88,0x4f89,0x4f8a]):
        if cp in cm: additions[0x06f0+i]=cm[cp]; additions[0x0660+i]=cm[cp]
    empty=cm[0x202c]
    for cp in (0x200c,0x200d,0x200e,0x200f,0x202a,0x202b,0x202d,0x202e,0x2066,0x2067,0x2068,0x2069):additions[cp]=empty
    for table in f['cmap'].tables:
        if table.isUnicode():table.cmap.update(additions)
    cm=f.getBestCmap()
    features=['languagesystem DFLT dflt;','languagesystem arab dflt;','languagesystem arab FAR;']
    for tag,form in [('isol','isolated'),('init','initial'),('medi','medial'),('fina','final')]:
        rules=[]
        for cp,shapes in forms.items():
            if form in shapes and cm.get(cp)!=shapes[form]:
                rules.append(f'sub {cm[cp]} by {shapes[form]};')
        if rules:features.append('feature '+tag+' { '+' '.join(rules)+' } '+tag+';')
    addOpenTypeFeaturesFromString(f,'\n'.join(features))
    missing=sorted({c for s in mapping.values() for c in s if ord(c)>127 and ord(c) not in cm and not c.isspace()})
    (ROOT/'font-missing.json').write_text(json.dumps(missing,ensure_ascii=False),'utf-8')
    print('Font missing:',ascii(''.join(missing)))
    f.save(ROOT/'fa_gamesub.ttf')

def helper(mapping):
    src=ROOT/'java/com/thegwchr/fuzzy';src.mkdir(parents=True,exist_ok=True)
    entries='\n'.join('        put('+json.dumps(k,ensure_ascii=True)+','+json.dumps(v,ensure_ascii=True)+');' for k,v in mapping.items())
    forms={}
    f=TTFont(ROOT/'fa_gamesub.ttf')
    for cp in f.getBestCmap():
        d=unicodedata.decomposition(chr(cp)).split()
        if len(d)==2 and d[0] in ('<isolated>','<final>','<initial>','<medial>'):
            forms.setdefault(int(d[1],16),{})[d[0][1:-1]]=cp
    shape_entries='\n'.join('        SHAPES.put(%d,new int[]{%s});'%(base,','.join(str(shapes.get(n,0)) for n in ('isolated','final','initial','medial'))) for base,shapes in forms.items())
    code='''package com.thegwchr.fuzzy;
import android.graphics.Typeface;
import android.widget.TextView;
import android.icu.text.Bidi;
import java.util.HashMap;
import java.util.Locale;
public final class FaTouchUi {
    public static void nativeReady(){try{System.loadLibrary("fuzzyfa");}catch(LinkageError e){android.util.Log.e("FaTouchUi","Native captions unavailable",e);}}
    private static boolean creditsShown;
    public static void showCredits(final android.app.Activity activity){
        final android.content.SharedPreferences prefs=activity.getSharedPreferences("fa_localization",0);
        if(creditsShown||prefs.getBoolean("hide_credits",false)||activity.isFinishing())return;
        creditsShown=true;
        android.app.AlertDialog dialog=new android.app.AlertDialog.Builder(activity)
          .setTitle("فارسی‌ساز GTA V")
          .setMessage("این فارسی‌سازی توسط AmirPhpDeveloper و تیم mobeegame ساخته شده است.\\n\\nبرای حمایت از پروژه، مخزن گیت‌هاب را استار کنید.")
          .setPositiveButton("مخزن پروژه ★",(d,w)->{try{activity.startActivity(new android.content.Intent(android.content.Intent.ACTION_VIEW,android.net.Uri.parse("https://github.com/AmirPhpDeveloper/gta-v-fuzzy-persian")));}catch(android.content.ActivityNotFoundException e){android.widget.Toast.makeText(activity,"مرورگری در دسترس نیست",android.widget.Toast.LENGTH_SHORT).show();}})
          .setNegativeButton("دیگر نمایش نده",(d,w)->prefs.edit().putBoolean("hide_credits",true).commit())
          .setNeutralButton("بعداً",(d,w)->{}).create();
        dialog.setOnShowListener(d->styleCredits(dialog.getWindow().getDecorView()));dialog.show();
    }
    private static void styleCredits(android.view.View view){if(view instanceof TextView){apply((TextView)view);view.setTextDirection(android.view.View.TEXT_DIRECTION_RTL);}if(view instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)view;for(int i=0;i<group.getChildCount();i++)styleCredits(group.getChildAt(i));}}
    private static final HashMap<String,String> MAP=new HashMap<>();
    private static final HashMap<Integer,int[]> SHAPES=new HashMap<>();
    private static Typeface face;
    static {
ENTRIES
SHAPE_ENTRIES
    }
    private static void put(String k,String v){MAP.put(k,v);}
    private static String key(String s){StringBuilder b=new StringBuilder();for(int i=0;i<s.length();i++){char c=s.charAt(i);if(Character.isLetterOrDigit(c)||c=='%'||c=='$')b.append(Character.toLowerCase(c));}return b.toString();}
    private static boolean custom(String s){for(int i=0;i<s.length();i++)if(s.charAt(i)>=0x4e00&&s.charAt(i)<=0x52ff)return true;return false;}
    public static String text(String s){if(s==null)return null;String t=MAP.get(key(s));if(t!=null)return t;
        String[][] prefixes={{"player: ","بازیکن: "},{"игрок: ","بازیکن: "},{"Tap [SPAWN] for direct model spawn: ","برای ظاهر کردن مستقیم مدل، دکمهٔ ظاهر کردن را بزنید: "},{"Нажмите [СПАВН] для прямого вызова модели: ","برای ظاهر کردن مستقیم مدل، دکمهٔ ظاهر کردن را بزنید: "},{"Rockstar ID ","شناسهٔ راکستار "}};
        for(String[] pair:prefixes)if(s.startsWith(pair[0]))return pair[1]+s.substring(pair[0].length());
        String[][] qualifiers={{"(Броня)","(زرهی)"},{"(Armored)","(زرهی)"},{"(Tank)","(تانک)"},{"(5-seater)","(پنج‌نفره)"},{"(Jetpack)","(جت‌پک)"},{"(Inflatable)","(بادی)"},{"(Yacht)","(تفریحی)"},{"(Seashark)","(جت‌اسکی)"},{"(Submersible)","(زیردریایی)"},{"(Tug)","(یدک‌کش)"},{"(Dump)","(معدن)"},{"(Mixer)","(بتن‌ریزی)"}};
        for(String[] pair:qualifiers)s=s.replace(pair[0],pair[1]);return s;}
    public static CharSequence ui(CharSequence s){if(s==null)return null;String raw=s.toString();String t=text(raw);if(custom(t))return "\\u202d"+t+"\\u202c";return t.equals(raw)?s:t;}
    private static int neighbor(String s,int i,int step){i+=step;while(i>=0&&i<s.length()){int c=s.charAt(i);int type=Character.getType(c);if(type!=Character.NON_SPACING_MARK&&c!=0x200d)return c;i+=step;}return -1;}
    private static String shape(String s){StringBuilder out=new StringBuilder();for(int i=0;i<s.length();i++){int c=s.charAt(i);int[] forms=SHAPES.get(c);if(forms==null){out.append((char)c);continue;}int[] prev=SHAPES.get(neighbor(s,i,-1)),next=SHAPES.get(neighbor(s,i,1));boolean left=prev!=null&&prev[2]!=0&&forms[1]!=0,right=next!=null&&next[1]!=0&&forms[2]!=0;int pos=left?(right?3:1):(right?2:0);out.append((char)(forms[pos]!=0?forms[pos]:c));}return out.toString();}
    public static String canvas(String s){return text(s);}
    public static void setText(TextView view,CharSequence text){view.setText(ui(text));apply(view);}
    public static void setHint(TextView view,CharSequence text){view.setHint(ui(text));apply(view);}
    public static void setTypeface(TextView view,Typeface ignored){apply(view);}
    public static void setTypeface(TextView view,Typeface ignored,int style){apply(view);view.setTypeface(face,style);}
    private static void apply(TextView view){try{if(face==null)face=Typeface.createFromAsset(view.getContext().getAssets(),"hud/fa_gamesub.ttf");view.setTypeface(face);}catch(RuntimeException e){android.util.Log.w("FaTouchUi","Font unavailable",e);}}
}
'''.replace('SHAPE_ENTRIES',shape_entries).replace('ENTRIES',entries)
    (src/'FaTouchUi.java').write_text(code,'utf-8')
    classes=ROOT/'java-classes';classes.mkdir(exist_ok=True)
    subprocess.run([r'C:\Program Files\Java\jdk-17\bin\javac.exe','-encoding','UTF-8','-source','8','-target','8','-cp',r'D:\Sdk\platforms\android-36\android.jar','-d',str(classes),str(src/'FaTouchUi.java')],check=True)
    dex=ROOT/'helper-dex';dex.mkdir(exist_ok=True)
    subprocess.run([r'D:\Sdk\build-tools\34.0.0\d8.bat','--min-api','30','--lib',r'D:\Sdk\platforms\android-36\android.jar','--output',str(dex),str(classes/'com/thegwchr/fuzzy/FaTouchUi.class')],check=True)

def smali():
    counts={}
    for variant in ('normal','trainer'):
        folder=ROOT/variant/'smali/com/thegwchr/fuzzy';counts[variant]={}
        for path in folder.glob('*.smali'):
            original=path.read_text('utf-8')
            if PKG in original:
                continue
            if path.name=='Tr.smali':
                pattern=r'(\.method static t\(\[Ljava/lang/String;\)Ljava/lang/String;).*?(\.end method)'
                replacement=r'\1\n    .locals 1\n    const/4 v0, 0x0\n    aget-object p0, p0, v0\n    invoke-static {p0}, '+PKG+r'->text(Ljava/lang/String;)Ljava/lang/String;\n    move-result-object p0\n    return-object p0\n\2'
                original,n=re.subn(pattern,replacement,original,flags=re.S);assert n==1
            if path.name=='GameUiFont.smali':original=original.replace('hud/chalet.otf','hud/fa_gamesub.ttf')
            out=[];n=0
            for line in original.splitlines():
                m=re.match(r'(\s*)invoke-virtual(?:/range)? \{([^}]+)\}, (\S+);->(\w+)\((.*)',line)
                if m and ' .. ' not in m[2]:
                    indent,registers,owner,method,signature=m.groups();regs=[r.strip() for r in registers.split(',')]
                    if method in ('setText','setHint') and signature=='Ljava/lang/CharSequence;)V' and owner in ('Landroid/widget/TextView','Landroid/widget/Button','Landroid/widget/EditText','Landroid/widget/CheckBox','Landroid/widget/Switch'):
                        line=indent+'invoke-static {'+registers+'}, '+PKG+'->'+method+'(Landroid/widget/TextView;Ljava/lang/CharSequence;)V';n+=1
                    elif (method=='measureText' and signature=='Ljava/lang/String;)F' and path.name=='TouchOverlay.smali') or (method=='drawText' and signature=='Ljava/lang/String;FFLandroid/graphics/Paint;)V'):
                        reg=regs[1]
                        out.extend([indent+'invoke-static/range {'+reg+' .. '+reg+'}, '+PKG+'->canvas(Ljava/lang/String;)Ljava/lang/String;',indent+'move-result-object '+reg]);n+=1
                out.append(line)
            path.write_text('\n'.join(out)+'\n','utf-8')
            if n:counts[variant][path.name]=n
        print(variant,'display hooks',sum(counts[variant].values()))
    (ROOT/'hook-report.json').write_text(json.dumps(counts,indent=2),'utf-8')

def font_hooks():
    for variant in ('normal','trainer'):
        total=0
        for path in (ROOT/variant/'smali/com/thegwchr/fuzzy').glob('*.smali'):
            source=path.read_text('utf-8')
            pattern=r'invoke-virtual \{([^}]+)\}, Landroid/widget/(?:TextView|Button|EditText|CheckBox|Switch);->setTypeface\((Landroid/graphics/Typeface;I?)\)V'
            source,n=re.subn(pattern,lambda m:'invoke-static {'+m[1]+'}, '+PKG+'->setTypeface(Landroid/widget/TextView;'+m[2]+')V',source)
            if n:path.write_text(source,'utf-8');total+=n
        print(variant,'typeface hooks',total)

def remove_widening_hooks():
    # Translate at final TextView boundaries. In-place CharSequence results can
    # widen a live String register and fail ART verification in later uses.
    for variant in ('normal','trainer'):
        for path in (ROOT/variant/'smali/com/thegwchr/fuzzy').glob('*.smali'):
            s=path.read_text('utf-8')
            pattern=r'    invoke-static/range \{([vp]\d+) \.\. \1\}, '+re.escape(PKG)+r'->ui\(Ljava/lang/CharSequence;\)Ljava/lang/CharSequence;\n    move-result-object \1\n'
            s,n=re.subn(pattern,'',s)
            if n:path.write_text(s,'utf-8')

def lifecycle_and_format_hooks():
    for variant in ('normal','trainer'):
        folder=ROOT/variant/'smali/com/thegwchr/fuzzy'
        path=folder/'Tr.smali';s=path.read_text('utf-8')
        start=s.index('.method static varargs f(');end=s.index('.end method',start)+len('.end method')
        replacement='''.method static varargs f([Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;
    .locals 2
    invoke-static {}, Ljava/util/Locale;->getDefault()Ljava/util/Locale;
    move-result-object v0
    invoke-static {p0}, Lcom/thegwchr/fuzzy/Tr;->t([Ljava/lang/String;)Ljava/lang/String;
    move-result-object p0
    invoke-static {v0, p0, p1}, Ljava/lang/String;->format(Ljava/util/Locale;Ljava/lang/String;[Ljava/lang/Object;)Ljava/lang/String;
    move-result-object p0
    return-object p0
.end method'''
        path.write_text(s[:start]+replacement+s[end:],'utf-8')
        path=folder/'LauncherActivity.smali';s=path.read_text('utf-8')
        if '->showCredits(Landroid/app/Activity;)V' not in s:
            assert '.method protected onPostResume()V' not in s
            s+='''
.method protected onPostResume()V
    .locals 0
    invoke-super {p0}, Landroid/app/Activity;->onPostResume()V
    invoke-static {p0}, Lcom/thegwchr/fuzzy/FaTouchUi;->showCredits(Landroid/app/Activity;)V
    return-void
.end method
'''
            path.write_text(s,'utf-8')

if __name__=='__main__':
    mapping=load_maps();font(mapping);helper(mapping);smali();font_hooks();remove_widening_hooks();lifecycle_and_format_hooks()
