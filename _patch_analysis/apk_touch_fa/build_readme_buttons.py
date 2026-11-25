"""Outline Persian labels so GitHub badges do not depend on remote RTL fonts."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
import arabic_reshaper
from bidi.algorithm import get_display
ROOT=Path(__file__).resolve().parents[2]
f=TTFont(ROOT/'assets/Vazirmatn-Bold.ttf');cm=f.getBestCmap();gs=f.getGlyphSet()
def button(name,label,width):
    glyphs=[cm[ord(c)] for c in get_display(arabic_reshaper.reshape(label))]
    bounds=[]
    for glyph in glyphs:
        pen=BoundsPen(gs);gs[glyph].draw(pen)
        if pen.bounds:bounds.append(pen.bounds)
    bottom=min(b[1] for b in bounds);top=max(b[3] for b in bounds)
    advance=sum(f['hmtx'][g][0] for g in glyphs)
    scale=min((width-32)/advance,22/(top-bottom));x=(width-advance*scale)/2;y=21+(top+bottom)*scale/2
    paths=[]
    for g in glyphs:
        pen=SVGPathPen(gs);gs[g].draw(TransformPen(pen,(scale,0,0,-scale,x,y)));paths.append(pen.getCommands());x+=f['hmtx'][g][0]*scale
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="42" viewBox="0 0 {width} 42" role="img" aria-label="{label}"><title>{label}</title><rect width="{width}" height="42" rx="7" fill="#168a45"/><path fill="#fff" d="'+ ' '.join(paths)+'"/></svg>'
    (ROOT/'assets'/name).write_text(svg,'utf-8')
button('language-fa.svg','فارسی',128)
button('download-fa.svg','دانلود فایل‌ها',180)
print('Outlined Persian buttons created.')
