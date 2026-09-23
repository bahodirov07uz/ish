from decimal import Decimal
from datetime import date, datetime
from django.utils import timezone
from django.db import transaction

from crm.models import Chiqim, ChiqimItem, ChiqimTuri
from xomashyo.models import XomashyoHarakat


def tolov_yozish(*, harakat, summa_uzs, sana, user, usd_kurs=None, izoh='', summa_usd=None):
    """
    Bitta XomashyoHarakat uchun to'lov yozadi.
    - select_for_update() bilan harakatni qulflaydi.
    - summa_uzs <= 0 yoki summa_uzs > harakat.qoldiq_uzs bo'lsa ValueError.
    - Chiqim + ChiqimItem yaratadi (crm.Chiqim post_save signali orqali Tranzaksiya avtomatik yoziladi).
    - Chaqiruvchi tomon transaction.atomic() ichida chaqiradi deb hisoblanadi.
    """
    harakat_id = harakat.pk if hasattr(harakat, 'pk') else harakat
    harakat = XomashyoHarakat.objects.select_for_update().get(pk=harakat_id)

    summa_uzs = Decimal(str(summa_uzs))
    if summa_uzs <= 0:
        raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak")

    if summa_uzs > harakat.qoldiq_uzs:
        xom_nomi = harakat.xomashyo.nomi if harakat.xomashyo else "Xomashyo"
        raise ValueError(
            f"{xom_nomi} uchun qoldiq: {harakat.qoldiq_uzs:,.0f} so'm, "
            f"kiritilgan: {summa_uzs:,.0f} so'm"
        )

    if not sana:
        sana = timezone.now().date()
    elif isinstance(sana, str):
        try:
            sana = datetime.strptime(sana, '%Y-%m-%d').date()
        except ValueError:
            sana = timezone.now().date()
    elif hasattr(sana, 'date') and not isinstance(sana, date):
        sana = sana.date()

    if usd_kurs is not None and str(usd_kurs).strip() != '':
        usd_kurs = Decimal(str(usd_kurs))
    else:
        usd_kurs = None

    if summa_usd is not None and str(summa_usd).strip() != '':
        summa_usd = Decimal(str(summa_usd))
    elif usd_kurs and usd_kurs > 0:
        summa_usd = (summa_uzs / usd_kurs).quantize(Decimal('0.0001'))
    else:
        summa_usd = None

    xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(
        name="Xomashyo to'lovi"
    )

    sana_display = sana.strftime('%d.%m.%Y') if hasattr(sana, 'strftime') else str(sana)
    harakat_sana_display = harakat.sana.strftime('%d.%m.%Y') if hasattr(harakat.sana, 'strftime') else str(harakat.sana)
    xom_nomi = harakat.xomashyo.nomi if harakat.xomashyo else 'Xomashyo'
    olchov = harakat.xomashyo.get_olchov_birligi_display() if harakat.xomashyo else ''

    chiqim_item_nomi = f"{xom_nomi} to'lovi — {harakat_sana_display}"
    auto_izoh = f"{xom_nomi} ({harakat.miqdori:g} {olchov}) uchun {summa_uzs:,.0f} so'm"
    if izoh:
        full_izoh = f"{auto_izoh}\nIzoh: {izoh}"
    else:
        full_izoh = auto_izoh

    chiqim = Chiqim.objects.create(
        name=f"Xomashyo to'lovi — {sana_display}",
        category=xomashyo_cat,
        price=summa_uzs,
        price_usd=summa_usd,
        usd_kurs=usd_kurs,
        izoh=full_izoh,
        created=sana,
        created_by=user,
    )

    item = ChiqimItem.objects.create(
        chiqim=chiqim,
        item_turi='xomashyo',
        name=chiqim_item_nomi,
        price_uzs=summa_uzs,
        price_usd=summa_usd,
        tolov_kursi=usd_kurs,
        xomashyo_harakat=harakat,
    )

    return chiqim, item


def taqsimlash(harakatlar, umumiy):
    """
    harakatlar: qoldig'i bor, kiritilgan tartibdagi ro'yxat.
    Qaytaradi: [(harakat, summa), ...].
    umumiy jami qoldiqdan oshsa ValueError.
    """
    qolgan = Decimal(str(umumiy))
    if qolgan <= 0:
        return []

    natija = []
    for h in harakatlar:
        if qolgan <= 0:
            break
        summa = min(h.qoldiq_uzs, qolgan)
        if summa > 0:
            natija.append((h, summa))
            qolgan -= summa
    if qolgan > 0:
        raise ValueError("To'lov summasi tanlangan xomashyolar qarzidan oshib ketdi")
    return natija


def tolov_yozish_kop(*, harakatlar, umumiy_uzs, sana, user, usd_kurs=None, izoh=''):
    """
    taqsimlash() natijasi bo'yicha: BITTA Chiqim, BITTA Transaction
    (A-bosqichda aniqlangan qoidaga ko'ra — Chiqim.save() signali orqali avtomatik yaratiladi),
    har bir ulush uchun bittadan ChiqimItem yaratadi.
    select_for_update() bilan barcha harakatlarni oldindan qulflaydi.
    """
    umumiy_uzs = Decimal(str(umumiy_uzs))
    if umumiy_uzs <= 0:
        raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak")

    harakat_ids = [h.pk if hasattr(h, 'pk') else h for h in harakatlar]
    locked_qs = XomashyoHarakat.objects.select_for_update().filter(id__in=harakat_ids)
    locked_dict = {h.id: h for h in locked_qs}
    ordered_harakatlar = [locked_dict[h_id] for h_id in harakat_ids if h_id in locked_dict]

    taqsimot = taqsimlash(ordered_harakatlar, umumiy_uzs)
    if not taqsimot:
        return None, []

    if not sana:
        sana = timezone.now().date()
    elif isinstance(sana, str):
        try:
            sana = datetime.strptime(sana, '%Y-%m-%d').date()
        except ValueError:
            sana = timezone.now().date()
    elif hasattr(sana, 'date') and not isinstance(sana, date):
        sana = sana.date()

    if usd_kurs is not None and str(usd_kurs).strip() != '':
        usd_kurs = Decimal(str(usd_kurs))
    else:
        usd_kurs = None

    if usd_kurs and usd_kurs > 0:
        summa_usd = (umumiy_uzs / usd_kurs).quantize(Decimal('0.0001'))
    else:
        summa_usd = None

    xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(
        name="Xomashyo to'lovi"
    )

    sana_display = sana.strftime('%d.%m.%Y') if hasattr(sana, 'strftime') else str(sana)

    izoh_parts = []
    for h, summa in taqsimot:
        xom_nomi = h.xomashyo.nomi if h.xomashyo else 'Xomashyo'
        olchov = h.xomashyo.get_olchov_birligi_display() if h.xomashyo else ''
        izoh_parts.append(f"{xom_nomi} ({h.miqdori:g} {olchov}) uchun {summa:,.0f} so'm")

    auto_izoh = "; ".join(izoh_parts)
    if izoh:
        full_izoh = f"{auto_izoh}\nIzoh: {izoh}"
    else:
        full_izoh = auto_izoh

    chiqim = Chiqim.objects.create(
        name=f"Xomashyo to'lovi — {sana_display}",
        category=xomashyo_cat,
        price=umumiy_uzs,
        price_usd=summa_usd,
        usd_kurs=usd_kurs,
        izoh=full_izoh,
        created=sana,
        created_by=user,
    )

    created_items = []
    for h, summa in taqsimot:
        h_sana_display = h.sana.strftime('%d.%m.%Y') if hasattr(h.sana, 'strftime') else str(h.sana)
        xom_nomi = h.xomashyo.nomi if h.xomashyo else 'Xomashyo'
        item_nomi = f"{xom_nomi} to'lovi — {h_sana_display}"
        item_usd = (summa / usd_kurs).quantize(Decimal('0.0001')) if usd_kurs and usd_kurs > 0 else None

        item = ChiqimItem.objects.create(
            chiqim=chiqim,
            item_turi='xomashyo',
            name=item_nomi,
            price_uzs=summa,
            price_usd=item_usd,
            tolov_kursi=usd_kurs,
            xomashyo_harakat=h,
        )
        created_items.append(item)

    return chiqim, created_items
