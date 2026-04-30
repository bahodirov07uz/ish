# xomashyo/models
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

class XomashyoCategory(models.Model):
    CATEGORY_TYPES = [
        ('real',    'Real xomashyo'),
        ('process', 'Jarayon xomashyo'),
    ]
    name   = models.CharField(max_length=200, verbose_name="Kategoriya nomi")
    tavsif = models.TextField(blank=True, verbose_name="Tavsif")
    tartib = models.IntegerField(default=0, verbose_name="Tartib raqami")
    turi   = models.CharField(
        max_length=20, choices=CATEGORY_TYPES,
        default='real', verbose_name="Kategoriya turi"
    )

    class Meta:
        verbose_name = "Xomashyo kategoriyasi"
        verbose_name_plural = "Xomashyo kategoriyalari"
        ordering = ['tartib', 'name']

    def __str__(self):
        return self.name



class YetkazibBeruvchi(models.Model):
    nomi            = models.CharField(max_length=255)
    telefon         = models.CharField(max_length=20)
    manzil          = models.TextField()
    inn             = models.CharField(max_length=20, blank=True)
    qisqacha_tavsif = models.TextField(blank=True)

    def __str__(self):
        return f"{self.nomi} — {self.telefon}"

    class Meta:
        verbose_name = "Yetkazib beruvchi"
        verbose_name_plural = "Yetkazib beruvchilar"


class Xomashyo(models.Model):
    OLCHOV_BIRLIKLARI = [
        ('kg',   'Kilogramm'),
        ('gr',   'Gramm'),
        ('lt',   'Litr'),
        ('dona', 'Dona'),
        ('dm',   'Desimetr'),
    ]
    HOLAT_CHOICES = [
        ('active',   'Faol'),
        ('deactive', 'Nofaol'),
        ('expired',  'Muddati o\'tgan'),
    ]

    nomi              = models.CharField(max_length=255)
    mahsulot          = models.ForeignKey(
        "crm.Product", on_delete=models.CASCADE, null=True, blank=True
    )
    category          = models.ForeignKey(
        XomashyoCategory, on_delete=models.PROTECT,
        related_name='xomashyolar', verbose_name="Kategoriya"
    )
    rang              = models.CharField(max_length=50, null=True, blank=True)
    miqdori           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    olchov_birligi    = models.CharField(max_length=20, choices=OLCHOV_BIRLIKLARI)
    minimal_miqdor    = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Oxirgi ma'lum narx (ma'lumotnoma uchun, haqiqiy narx XomashyoHarakatda)
    narxi             = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    narxi_usd         = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)

    yetkazib_beruvchi = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.SET_NULL, null=True, blank=True
    )
    qabul_qilingan_sana = models.DateField(auto_now_add=True)
    amal_qilish_muddati = models.DateField(null=True, blank=True)
    updated_at          = models.DateTimeField(auto_now=True)
    holati              = models.CharField(max_length=20, choices=HOLAT_CHOICES, default='active')
    qr_code             = models.CharField(max_length=100, blank=True)

    def __str__(self):
        if self.mahsulot:
            return f"{self.mahsulot.nomi} - {self.category.name} ({self.miqdori})"
        return f"{self.nomi} ({self.miqdori} {self.get_olchov_birligi_display()})"

    @property
    def is_jarayon_xomashyo(self):
        return self.category.turi == 'process'

    @property
    def kam_qolgan_mi(self):
        return self.miqdori <= self.minimal_miqdor

    def clean(self):
        if self.category.turi == 'process' and not self.mahsulot:
            raise ValidationError(
                f"{self.category.name} xomashyo uchun mahsulot ko'rsatilishi kerak!"
            )
        if self.category.turi == 'real' and self.mahsulot:
            raise ValidationError(
                f"{self.category.name} xomashyo uchun mahsulot ko'rsatilmasligi kerak!"
            )

    class Meta:
        verbose_name = "Xomashyo"
        verbose_name_plural = "Xomashyolar"


# ─────────────────────────────────────────────────────────────────
# XOMASHYO VARIANT
# ─────────────────────────────────────────────────────────────────

class XomashyoVariant(models.Model):
    xomashyo     = models.ForeignKey(
        Xomashyo, on_delete=models.CASCADE, related_name='variantlar'
    )
    rang         = models.CharField(max_length=50, null=True, blank=True)
    qalinlik     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    partiya_kodi = models.CharField(max_length=100, blank=True)
    yetkazuvchi  = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.CASCADE, null=True, blank=True
    )
    miqdori      = models.DecimalField(max_digits=10, decimal_places=2)
    narxi        = models.DecimalField(max_digits=15, decimal_places=2)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xomashyo varianti"
        verbose_name_plural = "Xomashyo variantlari"

    def __str__(self):
        return f"{self.xomashyo.nomi} | {self.rang or '-'} | {self.partiya_kodi}"


# ─────────────────────────────────────────────────────────────────
# XOMASHYO HARAKAT  — faqat ombor + narx (to'lov alohida)
# ─────────────────────────────────────────────────────────────────
class XomashyoHarakat(models.Model):
    HARAKAT_TURLARI = [
        ('kirim',            'Kirim'),
        ('chiqim',           'Chiqim'),
        ('inventarizatsiya', 'Inventarizatsiya'),
        ('qaytarish',        'Qaytarish'),
        ('taminlash',        'Ta\'minlash'),
    ]
    TOLOV_HOLATI = [
        ('tolanmagan', 'To\'lanmagan'),
        ('qisman',     'Qisman to\'langan'),
        ('toliq',      'To\'liq to\'langan'),
        ('kerak_emas', 'To\'lov kerak emas'),  # chiqim/inventarizatsiya uchun
    ]

    xomashyo         = models.ForeignKey(
        Xomashyo, on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Xomashyo"
    )
    xomashyo_variant = models.ForeignKey(
        XomashyoVariant, on_delete=models.CASCADE,
        related_name='harakatlar', null=True, blank=True
    )
    harakat_turi     = models.CharField(max_length=20, choices=HARAKAT_TURLARI)
    miqdori          = models.DecimalField(max_digits=10, decimal_places=2)
    sana             = models.DateField(default=timezone.now)

    # ── Narx (xomashyo kelgan kundagi) ──────────────────────────
    birlik_narx_uzs  = models.DecimalField(
        max_digits=20, decimal_places=2, default=0,
        verbose_name="Birlik narxi (UZS)"
    )
    birlik_narx_usd  = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        verbose_name="Birlik narxi (USD)"
    )
    jami_narx_uzs    = models.DecimalField(
        max_digits=20, decimal_places=2, default=0,
        verbose_name="Jami narxi (UZS)"
    )
    jami_narx_usd    = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        verbose_name="Jami narxi (USD)"
    )
    # Kelgan kunda dollar kursi (tarixiy ma'lumot)
    usd_kurs         = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="USD kursi (kelgan kunda)"
    )

    # ── To'lov holati ────────────────────────────────────────────
    # Faqat 'kirim' harakat turi uchun ahamiyatli
    tolov_holati     = models.CharField(
        max_length=20, choices=TOLOV_HOLATI, default='tolanmagan',
        verbose_name="To'lov holati"
    )
    tolangan_uzs     = models.DecimalField(
        max_digits=20, decimal_places=2, default=0,
        verbose_name="To'langan (UZS)"
    )
    tolangan_usd     = models.DecimalField(
        max_digits=20, decimal_places=4, default=0, null=True, blank=True,
        verbose_name="To'langan (USD)"
    )

    yetkazib_beruvchi = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.PROTECT, null=True, blank=True
    )
    foydalanuvchi    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    izoh             = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = "Xomashyo harakati"
        verbose_name_plural = "Xomashyo harakatlari"
        ordering = ['-sana']

    def __str__(self):
        nomi = self.xomashyo.nomi if self.xomashyo else '—'
        return f"{nomi} | {self.get_harakat_turi_display()} | {self.miqdori}"

    # ── Computed properties ──────────────────────────────────────

    @property
    def narxi(self):
        """
        Orqaga moslik uchun alias — birlik_narx_uzs ni qaytaradi.
        Admin va boshqa eski kod shu nomni ishlatadi.
        """
        return self.birlik_narx_uzs

    @property
    def qoldiq_uzs(self):
        """To'lanmagan qoldiq (UZS)"""
        return self.jami_narx_uzs - self.tolangan_uzs

    @property
    def qoldiq_usd(self):
        """To'lanmagan qoldiq (USD)"""
        if self.jami_narx_usd is not None:
            return self.jami_narx_usd - (self.tolangan_usd or Decimal('0'))
        return None

    @property
    def tolov_foizi(self):
        """Necha foiz to'langan"""
        if self.jami_narx_uzs > 0:
            return int((self.tolangan_uzs / self.jami_narx_uzs) * 100)
        return 0

    # ── Validatsiya ──────────────────────────────────────────────

    def clean(self):
        if self.xomashyo:
            if self.harakat_turi not in ('kirim', 'inventarizatsiya'):
                if self.miqdori > self.xomashyo.miqdori:
                    raise ValidationError("Xomashyoda yetarli miqdor yo'q")

    # ── Saqlash (faqat ombor yangilanadi) ────────────────────────

    def save(self, *args, **kwargs):
        """
        MUHIM: Bu yerda faqat OMBOR yangilanadi.
        Chiqim (pul) YARATILMAYDI — bu alohida jarayon.
        """
        self.clean()

        # Jami narxni avtomatik hisoblash (agar berilmagan bo'lsa)
        if not self.jami_narx_uzs and self.birlik_narx_uzs:
            self.jami_narx_uzs = self.birlik_narx_uzs * self.miqdori
        if self.birlik_narx_usd and not self.jami_narx_usd:
            self.jami_narx_usd = self.birlik_narx_usd * self.miqdori

        # Kirim uchun to'lov holati default
        if self.harakat_turi == 'kirim' and not self.pk:
            if self.jami_narx_uzs == 0:
                self.tolov_holati = 'kerak_emas'
            else:
                self.tolov_holati = 'tolanmagan'
        elif self.harakat_turi != 'kirim':
            self.tolov_holati = 'kerak_emas'

        is_new = self._state.adding
        super().save(*args, **kwargs)

        # Faqat yangi harakat uchun ombor yangilanadi
        if not is_new or not self.xomashyo:
            return

        if self.harakat_turi == 'kirim':
            self.xomashyo.miqdori += self.miqdori
        elif self.harakat_turi in ('chiqim', 'taminlash'):
            self.xomashyo.miqdori -= self.miqdori
        elif self.harakat_turi == 'qaytarish':
            self.xomashyo.miqdori += self.miqdori

        # MUHIM: Xomashyo.narxi va narxi_usd bu yerda O'ZGARTIRILMAYDI.
        # narxi — boshqa applar (CRM, ishlab chiqarish) ishlatiladigan
        #         qo'lda boshqariladigan ma'lumotnoma narxi.
        # Haqiqiy xarid narxi XomashyoHarakat.birlik_narx_uzs da saqlanadi.
        self.xomashyo.save(update_fields=['miqdori'])

    def tolov_yangilash(self):
        """
        ChiqimItem.save() chaqiradi — to'lov holati yangilanadi.
        Ombor O'ZGARMAYDI.
        """
        if self.harakat_turi != 'kirim':
            return

        jami_tolangan = self.tolovlar.aggregate(
            s=models.Sum('price_uzs')
        )['s'] or Decimal('0')

        self.tolangan_uzs = jami_tolangan

        if self.jami_narx_usd:
            jami_usd = self.tolovlar.aggregate(
                s=models.Sum('price_usd')
            )['s'] or Decimal('0')
            self.tolangan_usd = jami_usd

        if self.tolangan_uzs >= self.jami_narx_uzs:
            self.tolov_holati = 'toliq'
        elif self.tolangan_uzs > 0:
            self.tolov_holati = 'qisman'
        else:
            self.tolov_holati = 'tolanmagan'

        self.save(update_fields=['tolangan_uzs', 'tolangan_usd', 'tolov_holati'])


# ─────────────────────────────────────────────────────────────────
# CHIQIM TURI (kategoriya)
# ─────────────────────────────────────────────────────────────────

class ChiqimTuri(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Chiqim turi"
        verbose_name_plural = "Chiqim turlari"


