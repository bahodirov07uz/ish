from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum,F
from crm.models import Kirim
# Create your models here.


class Qaytarish(models.Model):
    """
    Sotuv ichidan mahsulot qaytarish.
 
    Zanjir (Qaytarish.save() chaqirilganda):
      1. super().save()                    → Qaytarish yozuvi saqlanadi
      2. sotuv_item.miqdor -= self.miqdor  → SotuvItem yangilanadi
      3. SotuvItem.save() avtomatik:
           - miqdor_farqi < 0  → variant.stock += abs(farqi)  [FIX 2: double yo'q]
           - sotuv.update_summa()          → jami/yakuniy yangilanadi
      4. Agar overpayment va 'returned':
           Kirim(summa=-overpayment) → _update_sotuv_tolangan() → tolangan_summa kamayadi
    """
    sotuv = models.ForeignKey(
        'Sotuv', on_delete=models.CASCADE,
        related_name="qaytarishlar", verbose_name="Sotuv"
    )
    sotuv_item = models.ForeignKey(
        'SotuvItem', on_delete=models.CASCADE,
        related_name="qaytarishlar", verbose_name="Sotuv elementi"
    )
    miqdor = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdor")
    birlik_narx = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Birlik narxi (qaytarish paytida)"
    )
    
    qaytarilgan_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Qaytarilgan summa (so'm)"
    )
    sabab = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Qaytarish sababi"
    )
    OVERPAYMENT_CHOICES = [
        ('none',     "Overpayment yo'q"),
        ('returned', "Ortiqcha pul qaytarildi"),
        ('kept',     "Ortiqcha pul keyingi sotuvga qoldirildi"),
    ]
    overpayment_holati = models.CharField(
        max_length=10,
        choices=OVERPAYMENT_CHOICES,
        default='none',
        verbose_name="Ortiqcha to'lov holati"
    )
    overpayment_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Ortiqcha to'lov miqdori"
    )
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    created_at = models.DateTimeField(auto_now_add=True)
    tolov_holati = models.CharField(
        max_length=20,
        choices=[
            ('kutilmoqda', "Pul qaytarilmagan"),
            ('tolandi',    "Pul qaytarildi"),
        ],
        default='kutilmoqda',
        verbose_name="To'lov holati"
    )
    tolangan_sana = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Pul qaytarilgan sana"
    )
    kirim = models.OneToOneField(
        'Kirim',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='qaytarish',
        verbose_name="Bog'liq kirim (storno)"
    )

    class Meta:
        verbose_name = "Qaytarish"
        verbose_name_plural = "Qaytarishlar"
        ordering = ['-sana']
 
    def __str__(self):
        return f"Qaytarish #{self.id} — {self.sotuv_item.variant} — {self.miqdor} ta"
 
    @classmethod
    def hisoblash(cls, sotuv_item, miqdor):
        """
        Qaytarish bajarilishidan OLDIN preview hisob-kitob.
        Hech qanday DB yozuvi yaratmaydi.
 
        Returns: dict  yoki  {'xato': str}
        """
        if miqdor <= 0:
            return {'xato': "Miqdor 0 dan katta bo'lishi kerak!"}
 
        already_returned = sotuv_item.qaytarishlar.aggregate(
            total=Sum('miqdor')
        )['total'] or 0
        max_returnable = sotuv_item.miqdor - already_returned
 
        if miqdor > max_returnable:
            return {
                'xato': (
                    f"Qaytarish miqdori ({miqdor} ta) ruxsat etilganidan "
                    f"({max_returnable} ta) ko'p!"
                )
            }
 
        sotuv           = sotuv_item.sotuv
        birlik_narx     = sotuv_item.narx
        qaytarish_summa = birlik_narx * Decimal(str(miqdor))
 
        yangi_jami    = sotuv.jami_summa - qaytarish_summa
        yangi_yakuniy = max(yangi_jami - sotuv.chegirma, Decimal('0'))
 
        # FIX 1: 'tolandan' → 'tolangan' (typo tuzatildi)
        tolangan     = sotuv.tolangan_summa
        hozirgi_qarz = sotuv.qarz_summa
 
        overpayment    = max(tolangan - yangi_yakuniy, Decimal('0'))
        yangi_qarz     = max(yangi_yakuniy - tolangan, Decimal('0'))
        qarz_kamayishi = min(qaytarish_summa, hozirgi_qarz)
 
        return {
            'xato':            None,
            'birlik_narx':     birlik_narx,
            'qaytarish_summa': qaytarish_summa,
            'yangi_jami':      yangi_jami,
            'yangi_yakuniy':   yangi_yakuniy,
            'hozirgi_yakuniy': sotuv.yakuniy_summa,
            'tolangan':        tolangan,          # FIX 1
            'hozirgi_qarz':    hozirgi_qarz,
            'yangi_qarz':      yangi_qarz,
            'qarz_kamayishi':  qarz_kamayishi,
            'overpayment':     overpayment,
            'max_returnable':  max_returnable,
        }
 
    def save(self, *args, **kwargs):
        from django.db import transaction
 
        is_new = self.pk is None
        if not is_new:
            super().save(*args, **kwargs)
            return
 
        sotuv_item = self.sotuv_item
        sotuv      = self.sotuv
 
        hisob = Qaytarish.hisoblash(sotuv_item, self.miqdor)
        if hisob['xato']:
            raise ValueError(hisob['xato'])
 
        self.birlik_narx       = hisob['birlik_narx']
        self.qaytarilgan_summa = hisob['qaytarish_summa']
        self.overpayment_summa = hisob['overpayment']
 
        with transaction.atomic():
            # 1. Qaytarish yozuvini saqlash
            super().save(*args, **kwargs)
 
            # 2. SotuvItem.miqdor ni kamaytirish.
            #    SotuvItem.save() ichida miqdor_farqi < 0 bo'lganda:
            #      variant.stock = F('stock') + abs(miqdor_farqi)  ← stock qaytariladi
            #      sotuv.update_summa()                             ← summa yangilanadi
            # FIX 2: Qaytarish.save() da alohida stock yoki update_summa KERAK EMAS
            sotuv_item.miqdor = sotuv_item.miqdor - self.miqdor
            sotuv_item.save()
 
            # 3. Overpayment → Kirim storno (manfiy)
            # FIX 3: Kirim — xuddi shu models.py dagi klass, import shart emas
            # FIX 9: manfiy summa — valyuta='uzs' va summa_usd ham hisoblanadi
            if hisob['overpayment'] > 0 and self.overpayment_holati == 'returned':
                op = hisob['overpayment']
                op_usd = Decimal('0')
                if sotuv.usd_kurs and sotuv.usd_kurs > 0:
                    op_usd = round(op / Decimal(str(sotuv.usd_kurs)), 4)
 
                Kirim.objects.create(
                    sotuv     = sotuv,
                    xaridor   = sotuv.xaridor,
                    summa     = -op,
                    summa_usd = -op_usd,
                    usd_kurs  = sotuv.usd_kurs or Decimal('0'),
                    valyuta   = 'uzs',
                    izoh      = (
                        f"Qaytarish #{self.id} — ortiqcha to'lov qaytarildi "
                        f"({int(op):,} so'm)"
                    ),
                )
                # Kirim.save() → _update_sotuv_tolangan() → tolangan_summa kamayadi
 
    def delete(self, *args, **kwargs):
        raise NotImplementedError(
            "Qaytarishni o'chirib bo'lmaydi. Admin panel orqali murojaat qiling."
        )
 
 