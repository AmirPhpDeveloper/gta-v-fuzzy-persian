"""Interactive front end for independent localization and dubbing patches."""
from pathlib import Path
import sys
from apply_patch import apply
ROOT=Path(__file__).resolve().parent.parent
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
print('Fuzzy Persian patch installer — نصب پچ فارسی GTA V')
print('1 = Persian localization / فارسی‌ساز')
print('2 = Persian dubbing only / فقط دوبله')
print('3 = Both / هر دو')
choice=input('Choose / انتخاب [1/2/3]: ').strip()
if choice not in ('1','2','3'):raise SystemExit('Invalid choice / انتخاب نامعتبر')
game=Path(input('Original game folder / مسیر پوشهٔ game اصلی: ').strip().strip('"'))
output=Path(input('Separate output game folder / مسیر پوشهٔ خروجی جداگانه: ').strip().strip('"'))
components=['localization','dubbing'] if choice=='3' else ['localization' if choice=='1' else 'dubbing']
try:
    for component in components:apply(ROOT/'manifests'/(component+'.json'),game,output,ROOT)
except Exception as error:raise SystemExit('ERROR / خطا: '+str(error))
print('Verified output ready. Copy it into the active game folder with the game and launcher closed.')
print('خروجی بررسی شد. بازی و لانچر را ببندید و فقط فایل‌های خروجی را در پوشهٔ فعال game جایگزین کنید.')
