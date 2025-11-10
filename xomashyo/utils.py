"""
Xomashyo bilan ishlash uchun yordamchi funksiyalar
Bu funksiyalar main app ichida joylashgan
"""

from decimal import Decimal
from django.utils.timezone import now
from .models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi


def xomashyo_sotib_olish(
    xomashyo_id,
    miqdor,
    narx=None,
    yetkazib_beruvchi_id=None,
    izoh='',
    foydalanuvchi=None
):
    """
    Xomashyo sotib olish funksiyasi
    
    Args:
        xomashyo_id: Xomashyo ID
        miqdor: Sotib olinayotgan miqdor (Decimal)
        narx: Umumiy narx (optional, agar berilmasa avtomatik hisoblanadi)
        yetkazib_beruvchi_id: Yetkazib beruvchi ID (optional)
        izoh: Qo'shimcha izoh (optional)
        foydalanuvchi: User obyekti (optional)
    
    Returns:
        tuple: (success: bool, message: str, xomashyo_harakat: XomashyoHarakat|None)
    """
    try:
        # Xomashyoni topish
        xomashyo = Xomashyo.objects.get(id=xomashyo_id)
        
        # Miqdorni tekshirish
        if miqdor <= 0:
            return False, "Miqdor 0 dan katta bo'lishi kerak!", None
        
        # Narxni hisoblash
        if narx is None:
            narx = xomashyo.narxi * Decimal(miqdor)
        else:
            narx = Decimal(narx)
        
        # Yetkazib beruvchi
        yetkazib_beruvchi = None
        if yetkazib_beruvchi_id:
            yetkazib_beruvchi = YetkazibBeruvchi.objects.get(id=yetkazib_beruvchi_id)
        
        # XomashyoHarakat yaratish
        # Bu avtomatik:
        # 1. Chiqim yaratadi (save metodida)
        # 2. Xomashyo miqdorini yangilaydi (signal orqali)
        xomashyo_harakat = XomashyoHarakat.objects.create(
            xomashyo=xomashyo,
            harakat_turi='kirim',
            miqdori=Decimal(miqdor),
            narxi=narx,
            izoh=izoh or f"{xomashyo.nomi} sotib olindi",
            yetkazib_beruvchi=yetkazib_beruvchi,
            foydalanuvchi=foydalanuvchi
        )
        
        success_message = (
            f"{xomashyo.nomi} ({miqdor} {xomashyo.get_olchov_birligi_display()}) "
            f"muvaffaqiyatli sotib olindi! "
            f"Jami: {int(narx):,} so'm"
        )
        
        return True, success_message, xomashyo_harakat
        
    except Xomashyo.DoesNotExist:
        return False, "Xomashyo topilmadi!", None
    except YetkazibBeruvchi.DoesNotExist:
        return False, "Yetkazib beruvchi topilmadi!", None
    except Exception as e:
        return False, f"Xatolik: {str(e)}", None


def xomashyo_ishlatish(xomashyo_id, miqdor, izoh='', foydalanuvchi=None):
    """
    Xomashyoni ishlatish (chiqim qilish)
    
    Args:
        xomashyo_id: Xomashyo ID
        miqdor: Ishlatiladigan miqdor (Decimal)
        izoh: Qo'shimcha izoh (optional)
        foydalanuvchi: User obyekti (optional)
    
    Returns:
        tuple: (success: bool, message: str, xomashyo_harakat: XomashyoHarakat|None)
    """
    try:
        xomashyo = Xomashyo.objects.get(id=xomashyo_id)
        miqdor_decimal = Decimal(miqdor)
        
        # Miqdorni tekshirish
        if miqdor_decimal <= 0:
            return False, "Miqdor 0 dan katta bo'lishi kerak!", None
        
        # Omborda yetarli xomashyo borligini tekshirish
        if xomashyo.miqdori < miqdor_decimal:
            return False, f"Omborda yetarli {xomashyo.nomi} yo'q! Mavjud: {xomashyo.miqdori}", None
        
        # Xomashyo chiqimi
        xomashyo_harakat = XomashyoHarakat.objects.create(
            xomashyo=xomashyo,
            harakat_turi='chiqim',
            miqdori=miqdor_decimal,
            izoh=izoh or f"{xomashyo.nomi} ishlatildi",
            foydalanuvchi=foydalanuvchi
        )
        
        success_message = (
            f"{xomashyo.nomi} ({miqdor_decimal} {xomashyo.get_olchov_birligi_display()}) "
            f"ishlatildi. Qolgan: {xomashyo.miqdori} {xomashyo.get_olchov_birligi_display()}"
        )
        
        return True, success_message, xomashyo_harakat
        
    except Xomashyo.DoesNotExist:
        return False, "Xomashyo topilmadi!", None
    except Exception as e:
        return False, f"Xatolik: {str(e)}", None


def xomashyo_minimal_tekshirish():
    """
    Minimal miqdordan kam xomashyolarni topish
    
    Returns:
        QuerySet: Kam xomashyolar ro'yxati
    """
    return Xomashyo.objects.filter(
        miqdori__lt=models.F('minimal_miqdor'),
        holati='active'
    )


def xomashyo_statistika(xomashyo_id=None):
    """
    Xomashyo statistikasi
    
    Args:
        xomashyo_id: Ma'lum bir xomashyo uchun (optional)
    
    Returns:
        dict: Statistika ma'lumotlari
    """
    from django.db.models import Sum, Count
    
    if xomashyo_id:
        # Ma'lum bir xomashyo uchun
        xomashyo = Xomashyo.objects.get(id=xomashyo_id)
        
        kirimlar = XomashyoHarakat.objects.filter(
            xomashyo=xomashyo,
            harakat_turi='kirim'
        ).aggregate(
            jami=Sum('miqdori'),
            soni=Count('id')
        )
        
        chiqimlar = XomashyoHarakat.objects.filter(
            xomashyo=xomashyo,
            harakat_turi='chiqim'
        ).aggregate(
            jami=Sum('miqdori'),
            soni=Count('id')
        )
        
        return {
            'xomashyo': xomashyo,
            'joriy_miqdor': xomashyo.miqdori,
            'kirim_jami': kirimlar['jami'] or 0,
            'kirim_soni': kirimlar['soni'],
            'chiqim_jami': chiqimlar['jami'] or 0,
            'chiqim_soni': chiqimlar['soni'],
        }
    else:
        # Barcha xomashyolar uchun
        return {
            'jami_xomashyo': Xomashyo.objects.count(),
            'faol_xomashyo': Xomashyo.objects.filter(holati='active').count(),
            'kam_xomashyo': xomashyo_minimal_tekshirish().count(),
        }