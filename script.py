"""
Kosib turidagi ishchilarning 15-26 may oralig'idagi ishlari bo'yicha hisobot.

Ishlatish (3 xil yo'l bilan):

1) Eng oson - to'g'ridan-to'g'ri skript sifatida (loyiha papkasi ichidan):
   python kosib_hisobot.py
   (pastdagi DJANGO_SETTINGS_MODULE qatorini o'z loyihangizga moslab qo'ying)

2) Management command sifatida:
   - Faylni app_name/management/commands/kosib_hisobot.py ga joylashtiring
   - python manage.py kosib_hisobot
   - (bu holda pastdagi os.environ/django.setup() qismini olib tashlang,
     Django buyruqni ishga tushirganda o'zi sozlaydi)

3) Shell orqali:
   python manage.py shell < kosib_hisobot.py
"""

import os
import django

# --- DIQQAT: bu qatorni o'z loyihangizga moslang ---
# manage.py faylini oching, ichida "DJANGO_SETTINGS_MODULE" qiymatini toping
# masalan: 'config.settings' yoki 'core.settings' yoki 'ish.settings'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
# ----------------------------------------------------

from datetime import date
from django.db.models import Sum

from crm.models import Ish  # <-- app nomini o'zingizga moslang


def kosib_hisobot(yil=None, boshlanish_kun=15, tugash_kun=25, oy=5):
    yil = yil or date.today().year
    boshlanish = date(yil, oy, boshlanish_kun)
    tugash = date(yil, oy, tugash_kun)

    qs = Ish.objects.filter(
        ishchi__turi__nomi="kosib",
        sana__gte=boshlanish,
        sana__lte=tugash,
    )

    # Umumiy summa va soni
    umumiy = qs.aggregate(
        jami_soni=Sum("soni"),
        jami_summa=Sum("narxi"),
    )

    print(f"\n=== KOSIB HISOBOTI: {boshlanish} — {tugash} ===\n")
    print(f"Jami soni:  {umumiy['jami_soni'] or 0} dona")
    print(f"Jami summa: {umumiy['jami_summa'] or 0} so'm\n")

    # Har bir mahsulot bo'yicha breakdown
    mahsulotlar = (
        qs.values("mahsulot__nomi")
        .annotate(
            soni=Sum("soni"),
            summa=Sum("narxi"),
        )
        .order_by("-summa")
    )

    print("--- Mahsulotlar bo'yicha ---")
    for m in mahsulotlar:
        nomi = m["mahsulot__nomi"]
        soni = m["soni"] or 0
        summa = m["summa"] or 0
        print(f"{nomi:30s} | {soni:5d} dona | {summa:>12} so'm")

    return {
        "jami": umumiy,
        "mahsulotlar": list(mahsulotlar),
    }


if __name__ == "__main__":
    kosib_hisobot()