import decimal
from decimal import Decimal
from django.utils import timezone
from xomashyo.models import XomashyoHarakat
from crm.models import Chiqim, ChiqimItem, ChiqimTuri


def tolov_yozish(items, user=None, sana=None, izoh='', chiqim_nomi=None):
    """
    Xomashyo kirimlari uchun to'lov (Chiqim + ChiqimItem) yaratish service funksiyasi.
    Tranzaksiya avtomatik ravishda Chiqim post_save signali orqali yaratiladi.

    :param items: list of dict:
        [
            {
                'harakat_id': 5,          # yoki 'harakat': harakat_instance
                'miqdor_uzs': 60000,
                'miqdor_usd': 5.0,        # ixtiyoriy
                'kurs': 12500,            # ixtiyoriy
            }, ...
        ]
    :param user: request.user yoki None
    :param sana: date yoki datetime (agar berilmasa timezone.now())
    :param izoh: qo'shimcha izoh
    :param chiqim_nomi: Chiqim nomi (agar berilmasa 'Xomashyo to\'lovi — DD.MM.YYYY')
    :return: tuple: (chiqim, auto_izoh, jami_uzs)
    """
    if not items:
        raise ValueError("Kamida bitta to'lov qatori kerak!")

    if not sana:
        sana = timezone.now()

    # ChiqimTuri "Xomashyo to'lovi" get_or_create
    xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(
        name="Xomashyo to'lovi"
    )

    jami_uzs = Decimal('0')
    jami_usd = Decimal('0')
    item_objects = []
    izoh_parts = []

    for row in items:
        harakat_val = row.get('harakat')
        if harakat_val and hasattr(harakat_val, 'id'):
            harakat_id = harakat_val.id
        else:
            harakat_id = row.get('harakat_id')

        if not harakat_id:
            raise ValueError("Xomashyo harakati ko'rsatilmagan!")

        # select_for_update bilan harakatni qulflash
        try:
            harakat = XomashyoHarakat.objects.select_for_update().select_related('xomashyo').get(id=harakat_id)
        except XomashyoHarakat.DoesNotExist:
            raise ValueError(f"Xomashyo harakati (id={harakat_id}) topilmadi!")

        try:
            miqdor_uzs = Decimal(str(row['miqdor_uzs']))
        except (decimal.InvalidOperation, TypeError, KeyError):
            raise ValueError("To'lov summasi (UZS) noto'g'ri kiritilgan!")

        if miqdor_uzs <= Decimal('0'):
            raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak!")

        # Qoldiqdan oshmasligi kerak
        if miqdor_uzs > harakat.qoldiq_uzs:
            nomi = harakat.xomashyo.nomi if harakat.xomashyo else f"Harakat #{harakat.id}"
            raise ValueError(
                f"{nomi} uchun qoldiq: "
                f"{harakat.qoldiq_uzs:,.0f} so'm, "
                f"kiritilgan: {miqdor_uzs:,.0f} so'm"
            )

        miqdor_usd_str = row.get('miqdor_usd')
        try:
            miqdor_usd = Decimal(str(miqdor_usd_str)) if miqdor_usd_str not in (None, '') else None
        except decimal.InvalidOperation:
            miqdor_usd = None

        kurs_str = row.get('kurs')
        try:
            kurs = Decimal(str(kurs_str)) if kurs_str not in (None, '') else None
        except decimal.InvalidOperation:
            kurs = None

        jami_uzs += miqdor_uzs
        if miqdor_usd:
            jami_usd += miqdor_usd

        olchov = harakat.xomashyo.get_olchov_birligi_display() if harakat.xomashyo else ''
        xomashyo_nomi = harakat.xomashyo.nomi if harakat.xomashyo else 'Xomashyo'
        izoh_parts.append(
            f"{xomashyo_nomi} ({harakat.miqdori:g} {olchov}) "
            f"uchun {miqdor_uzs:,.0f} so'm"
        )
        sana_display = harakat.sana.strftime('%d.%m.%Y') if hasattr(harakat.sana, 'strftime') else str(harakat.sana)
        item_objects.append({
            'harakat': harakat,
            'miqdor_uzs': miqdor_uzs,
            'miqdor_usd': miqdor_usd,
            'kurs': kurs,
            'name': f"{xomashyo_nomi} to'lovi — {sana_display}",
        })

    auto_izoh = "; ".join(izoh_parts)
    if izoh and izoh.strip():
        auto_izoh += f"\nIzoh: {izoh.strip()}"

    sana_label = sana.strftime('%d.%m.%Y') if hasattr(sana, 'strftime') else str(sana)
    name = chiqim_nomi or f"Xomashyo to'lovi — {sana_label}"

    chiqim = Chiqim.objects.create(
        name=name,
        category=xomashyo_cat,
        price=jami_uzs,
        price_usd=jami_usd if jami_usd else None,
        usd_kurs=item_objects[0]['kurs'] if item_objects else None,
        izoh=auto_izoh,
        created=sana,
        created_by=user,
    )

    for obj in item_objects:
        ChiqimItem.objects.create(
            chiqim=chiqim,
            item_turi='xomashyo',
            name=obj['name'],
            price_uzs=obj['miqdor_uzs'],
            price_usd=obj['miqdor_usd'],
            tolov_kursi=obj['kurs'],
            xomashyo_harakat=obj['harakat'],
            # save() ichida harakat.tolov_yangilash() chaqiriladi
            # ombor O'ZGARMAYDI
        )

    return chiqim, auto_izoh, jami_uzs
