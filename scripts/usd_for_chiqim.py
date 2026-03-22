import os
import django
import sys
from datetime import date
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') 
django.setup()

from decimal import Decimal
from crm.models import Chiqim,ChiqimItem,ChiqimTuri
from crm.views import get_usd_rate

def run():
    oylik_category, _ = ChiqimTuri.objects.get_or_create(name='oylik')

    kurs = Decimal(get_usd_rate())

    updated = 0
    chiqimlar = Chiqim.objects.filter(category__isnull=True,created=date.today())

    for ch in chiqimlar:
        if not ch.price:
            continue

        price_usd = ch.price / kurs
        print(ch)
        # # 🔹 Chiqim update
        
        ch.save(update_fields=['category', 'price_usd', 'usd_kurs'])
        items = ChiqimItem.objects.filter(chiqim=ch)

        for item in items:
            if item.price_uzs:
                item.price_usd = item.price_uzs / kurs
                item.tolov_kursi = kurs
                item.save(update_fields=['price_usd', 'tolov_kursi'])

        updated += 1

    print(f"{updated} ta chiqim 'oylik' ga o'tkazildi va USD hisoblandi")


        
if __name__ == "__main__":
    run()