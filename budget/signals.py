# budget/signals.py
"""
Chiqim va XomashyoHarakat saqlanganida Tranzaksiya avtomatik yaratiladi/yangilanadi/o'chiriladi.

Ulanish: budget/apps.py → BudgetConfig.ready() ichida import qilinadi.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


# ─────────────────────────────────────────────────────────────────
# CHIQIM → Tranzaksiya
# ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='crm.Chiqim')
def chiqim_tranzaksiya_sync(sender, instance, created, **kwargs):
    """
    Chiqim saqlanganda:
      - Yangi bo'lsa → Tranzaksiya yaratadi
      - Mavjud bo'lsa → Tranzaksiyani yangilaydi
    """
    from .models import Tranzaksiya

    # Kategoriya nomini olish (agar mavjud bo'lsa)
    kategoriya = ''
    if hasattr(instance, 'category') and instance.category:
        kategoriya = str(instance.category)
    elif hasattr(instance, 'tur') and instance.tur:
        kategoriya = str(instance.tur)

    # Ishchi (agar mavjud bo'lsa)
    ishchi = getattr(instance, 'ishchi', None)

    # Summa — modelingizga qarab field nomini to'g'rilang
    summa_uzs = getattr(instance, 'summa', None) or getattr(instance, 'summa_uzs', 0) or getattr(instance,'price',None) or getattr(instance,'price_uzs')
    summa_usd = getattr(instance, 'summa_usd', None) or getattr(instance,'price_usd',None) or getattr(instance,'price_usd')

    # Sana
    sana = getattr(instance, 'sana', None) or getattr(instance, 'created_at', None) or getattr(instance,'created',None)
    if hasattr(sana, 'date'):
        sana = sana.date()

    # Nomi/tavsif
    nomi = (
        getattr(instance, 'nomi', None)
        or getattr(instance, 'tavsif', None)
        or getattr(instance, 'izoh', None)
        or str(instance)
    )

    defaults = dict(
        manba='chiqim',
        ishchi=ishchi,
        foydalanuvchi=getattr(instance, 'yaratgan', None) or getattr(instance, 'foydalanuvchi', None),
        summa_uzs=summa_uzs,
        summa_usd=summa_usd,
        nomi=nomi[:500],
        kategoriya=kategoriya[:200],
        sana=sana,
    )

    Tranzaksiya.objects.update_or_create(
        chiqim=instance,
        defaults=defaults,
    )


@receiver(post_delete, sender='crm.Chiqim')
def chiqim_tranzaksiya_delete(sender, instance, **kwargs):
    """Chiqim o'chirilganda Tranzaksiyani ham o'chiradi (CASCADE bilan ham ishlaydi)."""
    from .models import Tranzaksiya
    Tranzaksiya.objects.filter(chiqim=instance).delete()


# ─────────────────────────────────────────────────────────────────
# XOMASHYO HARAKAT → Tranzaksiya
# (Faqat 'kirim' emas, xarid/chiqim harakatlari uchun)
# ─────────────────────────────────────────────────────────────────

# Xomashyo harakatining qaysi turlari xarajat hisoblanadi
XARAJAT_TURLARI = {'xarid', 'purchase', 'kirim_pul', 'chiqim'}  # → modelingizga moslashtiring


@receiver(post_save, sender='xomashyo.XomashyoHarakat')
def xomashyo_tranzaksiya_sync(sender, instance, created, **kwargs):
    """
    XomashyoHarakat saqlanganda:
      - Xarid/pul chiqimi bo'lsa → Tranzaksiya yaratadi/yangilaydi
      - Boshqa tur bo'lsa → mavjud tranzaksiyani o'chiradi
    """
    from .models import Tranzaksiya

    # Harakat turi xarajatga tegishlimi?
    harakat_tur = str(getattr(instance, 'harakat_tur', '') or getattr(instance, 'tur', '') or '')
    summa_uzs   = getattr(instance, 'narx', None) or getattr(instance, 'summa', None) or getattr(instance, 'summa_uzs', 0) or 0
    summa_usd   = getattr(instance, 'narx_usd', None) or getattr(instance, 'summa_usd', None)

    # Agar summa 0 yoki harakat xarajat emas → tranzaksiyani o'chir
    is_xarajat = (harakat_tur in XARAJAT_TURLARI) or (float(summa_uzs) > 0)
    if not is_xarajat:
        Tranzaksiya.objects.filter(xomashyo_harakat=instance).delete()
        return

    xomashyo = getattr(instance, 'xomashyo', None)
    kategoriya = str(xomashyo) if xomashyo else ''

    sana = getattr(instance, 'sana', None) or getattr(instance, 'created_at', None) or getattr(instance, 'created', None)
    if hasattr(sana, 'date'):
        sana = sana.date()

    nomi = (
        getattr(instance, 'izoh', None)
        or (f"{xomashyo} xaridi" if xomashyo else 'Xomashyo xaridi')
    )

    defaults = dict(
        manba='xomashyo',
        ishchi=None,
        foydalanuvchi=getattr(instance, 'yaratgan', None) or getattr(instance, 'foydalanuvchi', None),
        summa_uzs=summa_uzs,
        summa_usd=summa_usd,
        nomi=str(nomi)[:500],
        kategoriya=kategoriya[:200],
        sana=sana,
    )

    Tranzaksiya.objects.update_or_create(
        xomashyo_harakat=instance,
        defaults=defaults,
    )


@receiver(post_delete, sender='xomashyo.XomashyoHarakat')
def xomashyo_tranzaksiya_delete(sender, instance, **kwargs):
    """XomashyoHarakat o'chirilganda Tranzaksiyani ham o'chiradi."""
    from .models import Tranzaksiya
    Tranzaksiya.objects.filter(xomashyo_harakat=instance).delete()