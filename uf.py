from django.db.models import Sum
from datetime import date
from crm.models import Ish  # to'g'ri app nomini qo'ying

natija = Ish.objects.filter(
    ishchi__turi__nomi='kosib',
    sana__gte=date(2026, 6, 1),
    sana__lte=date(2026, 6, 26)
).aggregate(
    umumiy_soni=Sum('soni'),
    umumiy_narxi=Sum('narxi')
)

print(f"Umumiy soni: {natija['umumiy_soni'] or 0}")
print(f"Umumiy narxi: {natija['umumiy_narxi'] or 0}")