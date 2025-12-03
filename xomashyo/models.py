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

from crm.models import Chiqim

class Teri(models.Model):
    name = models.CharField(max_length=300)
    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    narxi = models.DecimalField(max_digits=15, decimal_places=2)

    def __str__(self):
        return self.name
    
class XomashyoCategory(models.Model):
    name = models.CharField(max_length=200, verbose_name="Kategoriya nomi")
    
class Xomashyo(models.Model):
    OLCHOV_BIRLIKLARI = [
        ('kg', 'Kilogramm'),
        ('gr', 'Gramm'),
        ('lt', 'Litr'),
        ('dona', 'Dona'),
        ('dm', 'detsimetr')
    ]
    nomi = models.CharField(max_length=255)
    category = models.ForeignKey(XomashyoCategory,on_delete=models.CASCADE)
    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    olchov_birligi = models.CharField(max_length=20, choices=OLCHOV_BIRLIKLARI)
    minimal_miqdor = models.DecimalField(max_digits=10, decimal_places=2)
    narxi = models.DecimalField(max_digits=15, decimal_places=2)
    yetkazib_beruvchi = models.ForeignKey('YetkazibBeruvchi', on_delete=models.SET_NULL, null=True)
    qabul_qilingan_sana = models.DateField(auto_now_add=True)
    amal_qilish_muddati = models.DateField(null=True, blank=True)
    holati = models.CharField(max_length=20, choices=[
        ('active', 'Faol'),
        ('deactive', 'Nofaol'),
        ('expired', 'Muddati otgan')
    ])
    qr_code = models.CharField(max_length=100, blank=True)

    def generate_qr_code(self):
        try:
            qr_info = f"""
            Xomashyo: {self.nomi}
            ID: {self.id}
            Miqdor: {self.miqdori} {self.get_olchov_birligi_display()}
            Qabul qilingan: {self.qabul_qilingan_sana}
            Muddati: {self.amal_qilish_muddati or 'Muddatsiz'}
            """
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_info.strip())
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            os.makedirs(qr_dir, exist_ok=True)
            filename = f'xomashyo_{self.id}.png'
            filepath = os.path.join(qr_dir, filename)
            img.save(filepath)
            self.qr_code = os.path.join('qr_codes', filename)
            self.save()
            return filepath
        except Exception as e:
            print(f"QR kod yaratishda xatolik: {str(e)}")
            return None

   
    
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
    xomashyo = models.ForeignKey(Xomashyo, on_delete=models.CASCADE)
    harakat_turi = models.CharField(max_length=20, choices=HARAKAT_TURLARI)
    miqdori = models.DecimalField(max_digits=10, decimal_places=2)
    izoh = models.TextField(blank=True)
    sana = models.DateTimeField(auto_now_add=True)
    narxi = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    yetkazib_beruvchi = models.ForeignKey(YetkazibBeruvchi, on_delete=models.SET_NULL, null=True, blank=True)
    foydalanuvchi = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)  # CustomUser

    def clean(self):
        if self.harakat_turi != 'kirim' and self.miqdori > self.xomashyo.miqdori:
            raise ValidationError("Omborda yetarli xomashyo mavjud emas!")

    def __str__(self):
        return f"{self.xomashyo.nomi} {self.miqdori} {self.harakat_turi}"

# main/models.py da XomashyoHarakat.save metodini yangilang

    def save(self, *args, **kwargs):
        """
        XomashyoHarakat saqlanganda avtomatik Chiqim yaratish
        """
        self.clean()  # Validatsiya
        is_new = self._state.adding  # Yangi obyekt ekanligini tekshirish
        
        super().save(*args, **kwargs)  # Avval saqlash
        
        # Faqat yangi kirim bo'lsa Chiqim yaratish
        if is_new and self.harakat_turi == 'kirim':
            from crm.models import Chiqim
            
            # Narxni hisoblash
            narx = int(self.narxi) if self.narxi else 0
            
            # O'lchov birligini olish
            olchov = self.xomashyo.get_olchov_birligi_display()
            
            # Chiqim yaratish
            Chiqim.objects.create(
                name=f"{self.xomashyo.nomi} ({self.miqdori} {olchov})",
                category=None,  # Yoki maxsus "Xomashyo" kategoriyasini yarating
                price=narx,
                created=self.sana.date() if self.sana else now().date()
            )

@receiver(post_save, sender=XomashyoHarakat)
def update_xomashyo_miqdori(sender, instance, **kwargs):
    if instance.harakat_turi == 'kirim':
        instance.xomashyo.miqdori += instance.miqdori
    else:
        instance.xomashyo.miqdori -= instance.miqdori
    instance.xomashyo.save()
    