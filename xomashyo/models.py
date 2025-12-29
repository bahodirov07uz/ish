# xomashyo/models
from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Sum
import os
from django.db.models.signals import post_save
from django.dispatch import receiver
import qrcode

class XomashyoCategory(models.Model):
    """
    Kategoriyalar:
    1. teri, astar, padoj - Real xomashyolar
    2. zakatovka, kroy, kosib - Ishlab chiqarish bosqichlari
    """
    name = models.CharField(max_length=200, verbose_name="Kategoriya nomi")
    tavsif = models.TextField(blank=True, verbose_name="Tavsif")
    tartib = models.IntegerField(default=0, verbose_name="Tartib raqami")
    
    # Kategoriya turi
    CATEGORY_TYPES = [
        ('real', 'Real xomashyo'),  # teri, astar, padoj
        ('process', 'Jarayon xomashyo'),  # zakatovka, kroy, kosib
    ]
    turi = models.CharField(
        max_length=20,
        choices=CATEGORY_TYPES,
        default='real',
        verbose_name="Kategoriya turi"
    )
    
    class Meta:
        verbose_name = "Xomashyo kategoriyasi"
        verbose_name_plural = "Xomashyo kategoriyalari"
        ordering = ['tartib', 'name']
    
    def __str__(self):
        return self.name

class Xomashyo(models.Model):
    OLCHOV_BIRLIKLARI = [
        ('kg', 'Kilogramm'),
        ('gr', 'Gramm'),
        ('lt', 'Litr'),
        ('dona', 'Dona'),
        ('dm', 'detsimetr')
    ]
    nomi = models.CharField(max_length=255)
    mahsulot = models.ForeignKey("crm.Product", on_delete=models.CASCADE, null=True, blank=True)

    category = models.ForeignKey(
        XomashyoCategory,
        on_delete=models.PROTECT,
        related_name='xomashyolar',
        verbose_name="Kategoriya"
    )
    rang  = models.CharField(max_length=50,null=True,blank=True)
    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    olchov_birligi = models.CharField(max_length=20, choices=OLCHOV_BIRLIKLARI)
    minimal_miqdor = models.DecimalField(max_digits=10, decimal_places=2,default=0)
    narxi = models.DecimalField(max_digits=15, decimal_places=2,null=True,blank=True)
    yetkazib_beruvchi = models.ForeignKey('YetkazibBeruvchi', on_delete=models.SET_NULL, null=True)
    qabul_qilingan_sana = models.DateField(auto_now_add=True)
    amal_qilish_muddati = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    holati = models.CharField(max_length=20, choices=[
        ('active', 'Faol'),
        ('deactive', 'Nofaol'),
        ('expired', 'Muddati otgan')
    ])
    qr_code = models.CharField(max_length=100, blank=True)

    def __str__(self):
        if self.mahsulot:
            return f"{self.mahsulot.nomi} - {self.category.name} ({self.miqdori})"
        return f"{self.nomi} ({self.miqdori} {self.get_olchov_birligi_display()})"
    
    @property
    def is_jarayon_xomashyo(self):
        """Jarayon xomashyosimi (zakatovka, kroy, kosib)?"""
        return self.category.turi == 'process'
    
    @property
    def kam_qolgan_mi(self):
        """Minimal miqdordan kam yoki yo'qmi?"""
        return self.miqdori <= self.minimal_miqdor
    
    def clean(self):
        """Validatsiya"""
        # Jarayon xomashyolar uchun mahsulot majburiy
        if self.category.turi == 'process' and not self.mahsulot:
            raise ValidationError(
                f"{self.category.name} xomashyo uchun mahsulot ko'rsatilishi kerak!"
            )
        
        # Real xomashyolar uchun mahsulot bo'lmasligi kerak
        if self.category.turi == 'real' and self.mahsulot:
            raise ValidationError(
                f"{self.category.name} xomashyo uchun mahsulot ko'rsatilmasligi kerak!"
            )
            
            
class XomashyoVariant(models.Model):
    xomashyo = models.ForeignKey(
        Xomashyo,
        on_delete=models.CASCADE,
        related_name='variantlar'
    )

    rang = models.CharField(max_length=50, null=True, blank=True)
    qalinlik = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    partiya_kodi = models.CharField(max_length=100, blank=True)
    yetkazuvchi = models.ForeignKey('YetkazibBeruvchi',on_delete=models.CASCADE,null=True, blank=True)

    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    narxi = models.DecimalField(max_digits=15, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xomashyo varianti"
        verbose_name_plural = "Xomashyo variantlari"

    def __str__(self):
        return f"{self.xomashyo.nomi} | {self.rang or '-'} | {self.partiya_kodi}"


class YetkazibBeruvchi(models.Model):
    nomi = models.CharField(max_length=255)
    telefon = models.CharField(max_length=20)
    manzil = models.TextField()
    inn = models.CharField(max_length=20, blank=True)
    qisqacha_tavsif = models.TextField(blank=True)

    def __str__(self):
        return self.nomi + self.telefon
    
class XomashyoHarakat(models.Model):
    HARAKAT_TURLARI = [
        ('kirim', 'Kirim'),
        ('chiqim', 'Chiqim'),
        ('inventarizatsiya', 'Inventarizatsiya'),
        ('qaytarish', 'Qaytarish')
    ]
    xomashyo = models.ForeignKey(Xomashyo, on_delete=models.CASCADE,null=True,blank=True, verbose_name="Xomashyo")

    xomashyo_variant = models.ForeignKey(
        XomashyoVariant,
        on_delete=models.CASCADE,
        related_name='harakatlar', null=True,blank=True
    )
    harakat_turi = models.CharField(max_length=20, choices=HARAKAT_TURLARI)
    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    sana = models.DateTimeField(auto_now_add=True)
    foydalanuvchi = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

    def clean(self):
        if self.harakat_turi != 'kirim' and self.miqdori > self.xomashyo_variant.miqdori:
            raise ValidationError("Xomashyo variantida yetarli miqdor yo‘q")

    def save(self, *args, **kwargs):
        self.clean()
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if not is_new:
            return

        if self.harakat_turi == 'kirim':
            self.xomashyo_variant.miqdori += self.miqdori
        else:
            self.xomashyo_variant.miqdori -= self.miqdori

        self.xomashyo_variant.save()


@receiver(post_save, sender=XomashyoHarakat)
def update_xomashyo_miqdori(sender, instance, **kwargs):
    if instance.harakat_turi == 'kirim':
        instance.xomashyo.miqdori += instance.miqdori
    else:
        instance.xomashyo.miqdori -= instance.miqdori
    instance.xomashyo.save()
    