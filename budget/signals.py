# budget/signals.py
"""
Chiqim va XomashyoHarakat saqlanganda avtomatik Tranzaksiya yaratadi/yangilaydi.
Qo'lda hech narsa qilish shart emas.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal


# ── CHIQIM → TRANZAKSIYA ─────────────────────────────────────────
@receiver(post_save, sender='crm.Chiqim')
def chiqim_tranzaksiya_yarat(sender, instance, created, **kwargs):
    from .models import Tranzaksiya

    # Kategoriya nomini olish
    kat = ''
    if instance.category:
        kat = instance.category.name

    # Ishchi: created_by user → Ishchi bog'lanishi yo'q,
    # shuning uchun foydalanuvchini saqlaymiz
    defaults = {
        'manba'         : 'chiqim',
        'summa_uzs'     : instance.price or Decimal('0'),
        'summa_usd'     : instance.price_usd or Decimal('0'),
        'nomi'          : instance.name or '—',
        'kategoriya'    : kat,
        'sana'          : instance.created,
        'foydalanuvchi' : instance.created_by,
    }

    Tranzaksiya.objects.update_or_create(
        chiqim=instance,
        defaults=defaults,
    )


@receiver(post_delete, sender='crm.Chiqim')
def chiqim_tranzaksiya_ochir(sender, instance, **kwargs):
    from .models import Tranzaksiya
    Tranzaksiya.objects.filter(chiqim=instance).delete()


# ── XOMASHYO HARAKAT → TRANZAKSIYA ──────────────────────────────
@receiver(post_save, sender='xomashyo.XomashyoHarakat')
def xomashyo_tranzaksiya_yarat(sender, instance, created, **kwargs):
    # Faqat 'kirim' harakati uchun — bu pul chiqimi
    if instance.harakat_turi != 'kirim':
        # Kirim bo'lmagan harakatlar uchun tranzaksiya o'chiriladi (agar bor bo'lsa)
        from .models import Tranzaksiya
        Tranzaksiya.objects.filter(xomashyo_harakat=instance).delete()
        return

    from .models import Tranzaksiya

    # Xomashyo nomi
    nomi = ''
    if instance.xomashyo:
        nomi = instance.xomashyo.nomi
    elif instance.xomashyo_variant:
        nomi = str(instance.xomashyo_variant)

    # Kategoriya
    kat = ''
    if instance.xomashyo and instance.xomashyo.category:
        kat = instance.xomashyo.category.name

    defaults = {
        'manba'           : 'xomashyo',
        'summa_uzs'       : instance.jami_narx_uzs or Decimal('0'),
        'summa_usd'       : instance.jami_narx_usd or Decimal('0'),
        'nomi'            : f"Xomashyo: {nomi} ({instance.miqdori} {instance.xomashyo.get_olchov_birligi_display() if instance.xomashyo else ''})",
        'kategoriya'      : kat,
        'sana'            : instance.sana,
        'foydalanuvchi'   : instance.foydalanuvchi,
    }

    Tranzaksiya.objects.update_or_create(
        xomashyo_harakat=instance,
        defaults=defaults,
    )


@receiver(post_delete, sender='xomashyo.XomashyoHarakat')
def xomashyo_tranzaksiya_ochir(sender, instance, **kwargs):
    from .models import Tranzaksiya
    Tranzaksiya.objects.filter(xomashyo_harakat=instance).delete()