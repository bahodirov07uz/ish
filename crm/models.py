# crm/models
from django.db import models,transaction
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Sum,F
from datetime import date
from django.utils import timezone
from xomashyo.models import Xomashyo,XomashyoHarakat,YetkazibBeruvchi
from decimal import Decimal
from django.conf import settings



class Category(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name="Nomi")
    slug = models.SlugField(unique=True, verbose_name="Slug")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsif")

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"

    def __str__(self):
        return self.name

class Product(models.Model):
    STATUS_CHOICES = [
        ('new', 'Yangi'),
        ('bestseller', "Ko'p sotiladigan"),
        ('sale', 'Chegirma'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Holati")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products", null=True, verbose_name="Kategoriya")
    nomi = models.CharField(max_length=255, verbose_name="Nomi",unique=True)
    description = models.TextField(verbose_name="Tavsif")
    narxi = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi")
    image = models.ImageField(upload_to="products/", verbose_name="Rasm",null=True,blank=True)
    avg_profit = models.PositiveIntegerField(default=0, verbose_name="O'rtacha foyda")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    narx_kosib = models.IntegerField(default=0, verbose_name="Kasb narxi")
    narx_zakatovka = models.IntegerField(default=0, verbose_name="Zakatovka narxi")
    narx_kroy = models.IntegerField(default=0, verbose_name="Kesish narxi")
    narx_rezak = models.IntegerField(default=0, verbose_name="Rezak kesish narxi")
    narx_pardoz = models.IntegerField(default=0, verbose_name="Pardoza narxi")
    soni = models.PositiveIntegerField(default=0,null=True,blank=True)

    teri_sarfi = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="1 ta mahsulot uchun teri sarfi (kg, m2 yoki dona)",
        verbose_name="Terı sarfi"
    )
    astar_sarfi = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="1 ta mahsulot uchun astar sarfi (kg, m2 yoki dona)",
        verbose_name="Astar sarfi"
    )
    class Meta:
        verbose_name = "Mahsulot"
        verbose_name_plural = "Mahsulotlar"
        constraints = [
            models.UniqueConstraint(fields=["category", "nomi"], name="uniq_product_category_nomi"),
        ]

        
    def product_total_stock(self):
        return sum(v.stock for v in self.productvariant_set.all())

    def update_total_quantity(self):
        """Mahsulotning umumiy miqdorini variantlar miqdorlari yig'indisiga moslab yangilash."""
        self.soni = self.variants.aggregate(total=models.Sum('stock'))['total'] or 0
        Product.objects.filter(pk=self.pk).update(soni=self.soni)
        
    @property
    def total_stock(self):
        """Umumiy mavjud mahsulot miqdorini qaytarish"""
        return sum(variant.stock for variant in self.variants.all())

    def __str__(self):
        return self.nomi

    def get_price_for_category(self, category_name):
        if category_name == "kosib":
            return self.narx_kosib
        elif category_name == "zakatovka":
            return self.narx_zakatovka
        elif category_name == "kroy":
            return self.narx_kroy
        elif category_name == "pardoz":
            return self.narx_pardoz
        elif category_name == "rezak":
            return self.narx_rezak
        
class ProductVariant(models.Model):
    TYPECHOICES = [
        ("dona","Dona"),
        ("set","Komplekt")
    ]
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE, 
        related_name="variants", 
        verbose_name="Mahsulot"
    )
    stock = models.PositiveIntegerField(default=0, null=True, verbose_name="Qoldiq")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name="Narxi")
    image = models.ImageField(upload_to='product/', null=True,blank=True, verbose_name="Rasm")
    
    # YANGI FIELDLAR
    rang = models.CharField(
        max_length=50, 
        blank=True, 
        default='', 
        verbose_name="Rang"
    )
    razmer = models.CharField(
        max_length=20, 
        blank=True, 
        default='', 
        verbose_name="Razmer"
    )
    type = models.CharField(max_length=60,choices=TYPECHOICES,default="set")
    feature = models.ManyToManyField('Feature',null=True,blank=True)
    sku = models.CharField(max_length=100,  blank=True, verbose_name="SKU")
    barcode = models.CharField(max_length=100,  blank=True, verbose_name="Shtrix kod")

    izoh = models.TextField(null=True,blank=True, verbose_name="izoh")
    
    class Meta:
        verbose_name = "Mahsulot varianti"
        verbose_name_plural = "Mahsulot variantlari"
        unique_together = ("product", "rang","razmer")

    def __str__(self):
        parts = [self.product.nomi]
        if self.rang:
            parts.append(f"Rang: {self.rang}")
        if self.razmer:
            parts.append(f"Razmer: {self.razmer}")
        return " | ".join(parts)

    def save(self, *args, **kwargs):
        if not self.sku:
            name_part = str(self.product.nomi).replace(" ", "").upper()
            color_part = (self.rang or "").replace(" ", "").upper()
            if self.type == "dona":
                self.sku = f"{name_part}-{color_part}-{self.razmer}-{self.type}"
            if  self.type == "set":
                self.sku = f"{name_part}-{color_part}-{self.type}"

        super().save(*args, **kwargs) # Saqlash oxirida bo'lsin
    
    def delete(self, *args, **kwargs):
        """Variant o'chirilganda mahsulotning umumiy miqdorini yangilash."""
        product = self.product
        super().delete(*args, **kwargs)
        product.update_total_quantity()

class IshchiCategory(models.Model):
    nomi = models.CharField(max_length=50, verbose_name="Nomi")

    class Meta:
        verbose_name = "Ishchi turi"
        verbose_name_plural = "Ishchi turlari"

    def __str__(self):
        return self.nomi

class Oyliklar(models.Model):
    sana = models.DateField(default=now, verbose_name="Sana")
    ishchi = models.ForeignKey(
        'Ishchi', on_delete=models.CASCADE, related_name='oyliklar', verbose_name="Ishchi"
    )
    oylik = models.IntegerField(null=True, verbose_name="Oylik")
    yopilgan = models.BooleanField(default=False, verbose_name="Yopilgan")
    hisoblangan = models.IntegerField(null=True, verbose_name="Hisoblangan oylik") 

 

    class Meta:
        verbose_name = "Oylik"
        verbose_name_plural = "Oyliklar"


    def __str__(self):
        return f"{self.ishchi.ism} - {self.sana} - {self.oylik}"

class EskiIsh(models.Model):
    ishchi = models.ForeignKey('Ishchi', on_delete=models.CASCADE, null=True, verbose_name="Ishchi")
    mahsulot = models.CharField(max_length=500, null=True, verbose_name="Mahsulot")
    sana = models.DateField(null=True, verbose_name="Sana")
    narxi = models.IntegerField(null=True, verbose_name="Narxi")
    soni = models.IntegerField(null=True, verbose_name="Soni")
    ishchi_oylik = models.ForeignKey(
        Oyliklar, on_delete=models.CASCADE, null=True, related_name='eski_ishlar', verbose_name="Ishchi oylik"
    )

    class Meta:
        verbose_name = "Eski ish"
        verbose_name_plural = "Eski ishlar"

    def __str__(self):
        return f"{self.ishchi.ism} - {self.mahsulot}"

class Ishchi(models.Model):

    ism = models.CharField(max_length=50, verbose_name="Ism")
    familiya = models.CharField(max_length=50, verbose_name="Familiya")
    maosh = models.IntegerField(verbose_name="Maosh")
    telefon = models.CharField(max_length=15, verbose_name="Telefon")
    turi = models.ForeignKey(IshchiCategory, on_delete=models.CASCADE, null=True, related_name='ish_turi', verbose_name="Ish turi")
    is_oylik_open = models.BooleanField(default=True, null=True, verbose_name="Oylik ochiq")
    yangi_oylik = models.IntegerField(default=0, null=True, verbose_name="Yangi oylik")
    oylik_yopilgan_sana = models.DateField(auto_now=True, null=True, verbose_name="Oylik yopilgan sana")
    current_oylik = models.OneToOneField(
        Oyliklar, on_delete=models.SET_NULL, null=True, blank=True, related_name="current_ishchi", verbose_name="Joriy oylik"
    )
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    eski_ishlar = models.ForeignKey(EskiIsh, on_delete=models.CASCADE, related_name='ishchilar', null=True, blank=True, verbose_name="Eski ishlar")

    class Meta:
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"

    def __str__(self):
        return f"{self.ism} {self.familiya}"

    def umumiy_oylik(self):
        umumiy_summa = sum(
            ish.narxi for ish in self.ishlar.filter(status='yangi')
        )
        return umumiy_summa

    @staticmethod
    def ishlar_soni():
        kosib_turi = Category.objects.get(nomi='kosib')
        return Ish.objects.filter(ishchi__turi=kosib_turi).aggregate(umumiy_soni=Sum('soni'))['umumiy_soni'] or 0
  
    def oy_mahsulotlar(self):
        """Joriy oyda ishchi har bir mahsulotdan qancha ishlab bergan"""
        current_month = now().month
        qs = self.ishlar.filter(status='yangi')

        return qs.values(
            'mahsulot__nomi'
        ).annotate(
            jami_soni=Sum('soni'),
            jami_summa=Sum('narxi')
        ).order_by('mahsulot__nomi')

class IshXomashyo(models.Model):
    """
    Ish va Xomashyo orasidagi bog'lanish
    Variant bilan ishlash imkonini beradi
    """
    
    ish = models.ForeignKey(
        'Ish',
        on_delete=models.CASCADE,
        related_name='ish_xomashyolar',
        verbose_name="Ish"
    )
    
    xomashyo = models.ForeignKey(
        'xomashyo.Xomashyo',
        on_delete=models.PROTECT,
        related_name='ish_xomashyolar',
        verbose_name="Xomashyo"
    )
    
    # Variant (ixtiyoriy)
    variant = models.ForeignKey(
        'xomashyo.XomashyoVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ish_xomashyolar',
        verbose_name="Variant"
    )
    
    miqdor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Miqdor"
    )
    
    birlik_narx = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name="Birlik narxi",
        null=True,
        blank=True
    )
    
    qoshilgan_sana = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Ish xomashyosi"
        verbose_name_plural = "Ish xomashyolari"
        ordering = ['-qoshilgan_sana']
    
    def __str__(self):
        if self.variant:
            return f"{self.ish} → {self.variant} ({self.miqdor})"
        return f"{self.ish} → {self.xomashyo.nomi} ({self.miqdor})"
    
    @property
    def jami_narx(self):
        """Ushbu xomashyo uchun umumiy narx"""
        if self.birlik_narx > 0:
            return self.miqdor * self.birlik_narx
        
        if self.variant:
            return self.miqdor * self.variant.narxi
        return self.miqdor * self.xomashyo.narxi
    
    def clean(self):
        """Validatsiya"""
        # Miqdorni tekshirish
        if self.miqdor <= 0:
            raise ValidationError("Miqdor musbat son bo'lishi kerak!")
        
        # Variant xomashyoga tegishli bo'lishi kerak
        if self.variant and self.variant.xomashyo != self.xomashyo:
            raise ValidationError("Variant tanlangan xomashyoga tegishli emas!")
        
        # FAQAT REAL XOMASHYOLAR UCHUN miqdorni tekshirish
        # Jarayon xomashyolar (zakatovka, kroy, kosib) uchun tekshirish KERAK EMAS
        if hasattr(self.xomashyo, 'is_jarayon_xomashyo') and self.xomashyo.is_jarayon_xomashyo:
            # Jarayon xomashyo - validatsiya kerak emas
            return
        
        # Real xomashyo uchun miqdorni tekshirish
        if self.variant:
            # Variant orqali
            if self.miqdor > self.variant.miqdori:
                raise ValidationError(
                    f"Variantda yetarli miqdor yo'q! "
                    f"Mavjud: {self.variant.miqdori}, Talab: {self.miqdor}"
                )
        else:
            # Oddiy xomashyo
            if self.miqdor > self.xomashyo.miqdori:
                raise ValidationError(
                    f"Omborda yetarli miqdor yo'q! "
                    f"Mavjud: {self.xomashyo.miqdori}, Talab: {self.miqdor}"
                )
    
    def save(self, *args, **kwargs):
        """
        Saqlashda xomashyo/variant miqdorini kamaytirish
        DIQQAT: Faqat real xomashyolar uchun!
        """
        # Agar birlik_narx bo'sh bo'lsa, avtomatik to'ldirish
        if not self.birlik_narx or self.birlik_narx == 0:
            if self.variant:
                self.birlik_narx = self.variant.narxi
            else:
                self.birlik_narx = self.xomashyo.narxi
        
        # Validatsiya
        self.clean()
        
        is_new = self._state.adding
        
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Faqat yangi yozuv uchun
            if not is_new:
                return
            
            # FAQAT REAL XOMASHYOLAR uchun miqdorni kamaytirish
            # Jarayon xomashyolar (zakatovka, kroy, kosib) view'da kamaytiriladi
            is_jarayon = hasattr(self.xomashyo, 'is_jarayon_xomashyo') and self.xomashyo.is_jarayon_xomashyo
            
            if not is_jarayon:
                # Real xomashyo
                if self.variant:
                    # Variant miqdorini kamaytirish
                    # View'da allaqachon kamaytirilgan bo'lishi mumkin
                    # Shuning uchun hech narsa qilmaymiz
                    pass
                else:
                    # Oddiy xomashyo miqdorini kamaytirish
                    self.xomashyo.save(update_fields=['miqdori', 'updated_at'])

class Ish(models.Model):
    STATUS_CHOICES = [
        ('yangi','Yangi'),
        ('yopilgan','Yopilgan'),
    ]
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Mahsulot")
    soni = models.IntegerField(null=True, verbose_name="Soni")
    sana = models.DateField(null=True, default=timezone.now(), verbose_name="Sana")
    narxi = models.IntegerField(null=True, blank=True, verbose_name="Narxi")
    status = models.CharField(max_length=30,choices=STATUS_CHOICES,null=True,blank=True)
    ishchi = models.ForeignKey(
        Ishchi, on_delete=models.CASCADE, null=True,blank=True, related_name='ishlar', verbose_name="Ishchi"
    )

    # Xomashyolar bilan bog'lanish (Through model orqali)
    xomashyolar = models.ManyToManyField(
        'xomashyo.Xomashyo',
        through='IshXomashyo',
        related_name='ishlar',
        verbose_name="Xomashyolar"
    )
    
    class Meta:
        verbose_name = "Ish"
        verbose_name_plural = "Ishlar"

    def __str__(self):
        return self.mahsulot.nomi

    def save(self, *args, **kwargs):
        if self.ishchi and self.ishchi.turi:
            if self.ishchi.turi.nomi == "kosib":
                self.narxi = self.mahsulot.narx_kosib * int(self.soni)
            elif self.ishchi.turi.nomi == "zakatovka":
                self.narxi = self.mahsulot.narx_zakatovka * int(self.soni)
            elif self.ishchi.turi.nomi == "kroy":
                self.narxi = self.mahsulot.narx_kroy * int(self.soni)
            elif self.ishchi.turi.nomi == "pardozchi" or 'pardoz':
                self.narxi = self.mahsulot.narx_pardoz * int(self.soni)
            elif self.ishchi.turi.nomi == "rezak":
                self.narxi = self.mahsulot.narx_rezak * int(self.soni)
                
        super().save(*args, **kwargs)
        if self.ishchi and self.ishchi.turi and self.ishchi.turi.nomi == "kosib":
            from django.db.models import Sum
            jami = self.__class__.objects.filter(
                mahsulot=self.mahsulot,
                ishchi__turi__nomi="kosib"
            ).aggregate(Sum('soni'))['soni__sum'] or 0
            self.mahsulot.soni = jami
            self.mahsulot.save()
            


class ChiqimTuri(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nomi")

    class Meta:
        verbose_name = "Chiqim turi"
        verbose_name_plural = "Chiqim turlari"

    def __str__(self):
        return self.name

# ─────────────────────────────────────────────────────────────────
# CHIQIM  — faqat pul chiqishi
# ─────────────────────────────────────────────────────────────────
class Chiqim(models.Model):
    name       = models.CharField(max_length=500)
    category   = models.ForeignKey(
        ChiqimTuri, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Narx ikki valyutada
    price      = models.DecimalField(
        max_digits=20, decimal_places=2, default=0,
        verbose_name="Jami (UZS)"
    )
    price_usd  = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        verbose_name="Jami (USD)"
    )
    # To'lov sanasidagi kurs
    usd_kurs   = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="USD kursi (to'lov kuni)"
    )

    izoh       = models.TextField(blank=True)
    created    = models.DateField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    def __str__(self):
        return f"{self.name} — {self.price:,.0f} so'm"

    class Meta:
        verbose_name = "Chiqim"
        verbose_name_plural = "Chiqimlar"
        ordering = ['-created']


class ChiqimItem(models.Model):
    ITEM_TURI = [
        ('xomashyo', 'Xomashyo to\'lovi'),
        ('boshqa',   'Boshqa chiqim'),
        ('oylik','Xodim oyliklari'),
    ]

    chiqim    = models.ForeignKey(
        Chiqim, on_delete=models.CASCADE, related_name='itemlar'
    )
    item_turi = models.CharField(max_length=20, choices=ITEM_TURI)
    name      = models.CharField(max_length=500)

    # To'lov miqdori (bu to'lov uchun)
    price_uzs = models.DecimalField(
        max_digits=20, decimal_places=2,
        verbose_name="To'lov miqdori (UZS)"
    )
    price_usd = models.DecimalField(
        max_digits=20, decimal_places=4, null=True, blank=True,
        verbose_name="To'lov miqdori (USD)"
    )
    # To'lov sanasidagi kurs (harakat.usd_kurs dan farq qilishi mumkin)
    tolov_kursi = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name="To'lov kuni kursi"
    )

    # Bog'liq xomashyo harakati (FK — bir harakatga ko'p to'lov mumkin)
    xomashyo_harakat = models.ForeignKey(
        XomashyoHarakat,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tolovlar',  # harakat.tolovlar.all()
        verbose_name="Xomashyo harakati"
    )

    # Boshqa chiqim uchun
    yetkazib_beruvchi = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"{self.name} — {self.price_uzs:,.0f} so'm"

    def save(self, *args, **kwargs):
        """
        ChiqimItem saqlanganida bog'liq XomashyoHarakat.tolov_holati yangilanadi.
        Ombor O'ZGARMAYDI.
        """
        super().save(*args, **kwargs)

        # Agar xomashyo to'lovi bo'lsa — harakatni yangilash
        if self.item_turi == 'xomashyo' and self.xomashyo_harakat_id:
            self.xomashyo_harakat.tolov_yangilash()

    def delete(self, *args, **kwargs):
        harakat = self.xomashyo_harakat
        super().delete(*args, **kwargs)
        # O'chirilgandan keyin ham harakatni yangilash
        if harakat:
            harakat.tolov_yangilash()

    class Meta:
        verbose_name = "Chiqim elementlari"
        verbose_name_plural = "Chiqim elementlari"
        
        
class Xaridor(models.Model):
    """Xaridor ma'lumotlari"""
    ism = models.CharField(max_length=150, verbose_name="Ism")
    telefon = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon")
    manzil = models.CharField(max_length=255, blank=True, null=True, verbose_name="Manzil")
    izoh = models.TextField(blank=True, null=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")

    class Meta:
        verbose_name = "Xaridor"
        verbose_name_plural = "Xaridorlar"

    def __str__(self):
        return self.ism

class Sotuv(models.Model):
    """Asosiy sotuv - bir xaridor uchun bir to'liq buyurtma"""
    xaridor = models.ForeignKey(
        'Xaridor', 
        on_delete=models.CASCADE, 
        related_name="sotuvlar", 
        verbose_name="Xaridor"
    )
    jami_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Jami summa (so'm)"
    )
    chegirma = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Chegirma (so'm)"
    )
    yakuniy_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="Yakuniy summa (so'm)"
    )
    
    # === YANGI USD FIELDLAR ===
    usd_kurs = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="USD kursi (sotuv paytida)",
        help_text="CBU dan olingan USD kursi"
    )
    jami_summa_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Jami summa (USD)"
    )
    yakuniy_summa_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Yakuniy summa (USD)"
    )
    # === YANGI: To'langan summa (qarz tizimi uchun) ===
    tolangan_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="To'langan summa (so'm)"
    )
    # =========================
    
    tolov_holati = models.CharField(
        max_length=20,
        choices=[
            ('tolandi', 'To\'landi'),
            ('qisman', 'Qisman to\'landi'),
            ('tolanmadi', 'To\'lanmadi'),
        ],
        default='tolanmadi',
        verbose_name="To'lov holati"
    )
    izoh = models.TextField(blank=True, null=True, verbose_name="Izoh")
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratildi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilandi")

    class Meta:
        verbose_name = "Sotuv"
        verbose_name_plural = "Sotuvlar"
        ordering = ['-sana']

    def __str__(self):
        return f"#{self.id} - {self.xaridor.ism} - {self.yakuniy_summa} so'm"

    @property
    def qarz_summa(self):
        """Hozirgi qarz miqdori"""
        return max(self.yakuniy_summa - self.tolangan_summa, 0)

    @property
    def qarz_summa_usd(self):
        """Qarz USD da"""
        if self.usd_kurs and self.usd_kurs > 0:
            return round(self.qarz_summa / self.usd_kurs, 4)
        return 0

    def update_summa(self):
        """Sotuv ichidagi barcha itemlarni hisoblash"""
        self.jami_summa = self.items.aggregate(
            total=Sum(F('narx') * F('miqdor'))
        )['total'] or 0
        self.yakuniy_summa = self.jami_summa - self.chegirma
        
        # USD summalarini hisoblash
        if self.usd_kurs and self.usd_kurs > 0:
            self.jami_summa_usd = round(Decimal(str(self.jami_summa)) / Decimal(str(self.usd_kurs)), 4)
            self.yakuniy_summa_usd = round(Decimal(str(self.yakuniy_summa)) / Decimal(str(self.usd_kurs)), 4)
        
        # To'lov holatini yangilash
        self._update_tolov_holati()
        
        self.save(update_fields=['jami_summa', 'yakuniy_summa', 'jami_summa_usd', 
                                  'yakuniy_summa_usd', 'tolov_holati', 'updated_at'])

    def _update_tolov_holati(self):
        """To'langan summaga qarab holatni avtomatik yangilash"""
        if self.tolangan_summa >= self.yakuniy_summa:
            self.tolov_holati = 'tolandi'
        elif self.tolangan_summa > 0:
            self.tolov_holati = 'qisman'
        else:
            self.tolov_holati = 'tolanmadi'

  
class SotuvItem(models.Model):
    """Sotuv tarkibidagi alohida mahsulot"""
    sotuv = models.ForeignKey(
        Sotuv, on_delete=models.CASCADE, 
        related_name="items", verbose_name="Sotuv"
    )
    mahsulot = models.ForeignKey(
        'Product', on_delete=models.PROTECT, 
        related_name="sotuv_items", verbose_name="Mahsulot"
    )
    variant = models.ForeignKey(
        'ProductVariant', on_delete=models.PROTECT,
        related_name="sotuv_items", verbose_name="Variant"
    )
    miqdor = models.PositiveIntegerField(verbose_name="Miqdor")
    narx = models.DecimalField(
        max_digits=10, decimal_places=2, 
        verbose_name="Birlik narxi (so'm)"
    )
    # === YANGI USD NARX ===
    narx_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        verbose_name="Birlik narxi (USD)",
        help_text="Agar USD da kiritilgan bo'lsa"
    )
    narx_turi = models.CharField(
        max_length=3, 
        choices=[('uzs', "So'm"), ('usd', 'USD')],
        default='uzs',
        verbose_name="Narx valyutasi"
    )
    # =====================
    jami = models.DecimalField(
        max_digits=12, decimal_places=2, 
        editable=False, verbose_name="Jami summa (so'm)"
    )
    jami_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        editable=False, verbose_name="Jami summa (USD)"
    )
    izoh = models.CharField(max_length=255, blank=True, null=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Sotuv elementi"
        verbose_name_plural = "Sotuv elementlari"

    def __str__(self):
        return f"{self.variant} - {self.miqdor} ta - {self.narx} so'm"

    def save(self, *args, **kwargs):
        # Sotuv kursidan foydalanish
        usd_kurs = self.sotuv.usd_kurs if self.sotuv.usd_kurs else Decimal('0')
        
        narx =  Decimal(str(self.narx or 0))
        miqdor = int(self.miqdor or 0)


        # Narxni hisoblash (valyutaga qarab)
        if self.narx_turi == 'usd' and usd_kurs > 0:
            self.narx_usd = self.narx 
            self.narx = round(Decimal(str(self.narx)) * usd_kurs, 2) 
        elif usd_kurs > 0:
            self.narx_usd = round(Decimal(str(self.narx)) / usd_kurs, 4)
        
        narx = Decimal(str(self.narx or 0))
        
        
        # Jami summalar
        self.jami = Decimal(str(self.narx)) * Decimal(str(self.miqdor))
        if usd_kurs > 0:
            self.jami_usd = round(self.jami / usd_kurs, 4)
        
        # Yangi item ekanligini tekshirish
        is_new = self.pk is None
        old_miqdor = 0
        
        if not is_new:
            old_item = SotuvItem.objects.get(pk=self.pk)
            old_miqdor = old_item.miqdor
        
        # Stock tekshirish
        if is_new:
            if self.variant.stock < self.miqdor:
                raise ValueError(
                    f"Omborda yetarli {self.variant} yo'q! "
                    f"Mavjud: {self.variant.stock} ta, Kerak: {self.miqdor} ta"
                )
        else:
            miqdor_farqi = self.miqdor - old_miqdor
            if miqdor_farqi > 0:
                if self.variant.stock < miqdor_farqi:
                    raise ValueError(
                        f"Omborda yetarli {self.variant} yo'q! "
                        f"Mavjud: {self.variant.stock} ta"
                    )
        
        super().save(*args, **kwargs)
        
        # Stockni yangilash
        from django.db import transaction
        with transaction.atomic():
            self.variant.refresh_from_db()
            if is_new:
                self.variant.stock = F('stock') - self.miqdor
            else:
                miqdor_farqi = self.miqdor - old_miqdor
                if miqdor_farqi > 0:
                    self.variant.stock = F('stock') - miqdor_farqi
                elif miqdor_farqi < 0:
                    self.variant.stock = F('stock') + abs(miqdor_farqi)
            self.variant.save()
            self.variant.refresh_from_db()
        
        self.mahsulot.update_total_quantity()
        self.sotuv.update_summa()

    def delete(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            self.variant.stock = F('stock') + self.miqdor
            self.variant.save()
            self.variant.refresh_from_db()
            self.mahsulot.update_total_quantity()
            sotuv = self.sotuv
            super().delete(*args, **kwargs)
            sotuv.update_summa()

class Kirim(models.Model):
    """Sotuv to'lovlari (bir sotuv uchun bir nechta to'lov bo'lishi mumkin)"""
    sotuv = models.ForeignKey(
        Sotuv, on_delete=models.CASCADE, 
        related_name="kirimlar",  # MUHIM: "kirim" dan "kirimlar" ga o'zgardi
        verbose_name="Sotuv",
        null=True,blank=True
    )
    xaridor = models.ForeignKey(
        Xaridor, on_delete=models.CASCADE, verbose_name="Xaridor"
    )
    summa = models.DecimalField(
        max_digits=12, decimal_places=2, 
        verbose_name="Summa (so'm)"
    )
    # === YANGI USD FIELDLAR ===
    summa_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Summa (USD)"
    )
    usd_kurs = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="USD kursi"
    )
    valyuta = models.CharField(
        max_length=3,
        choices=[('uzs', "So'm"), ('usd', 'USD')],
        default='uzs',
        verbose_name="To'lov valyutasi"
    )
    # =========================
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    izoh = models.TextField(null=True, blank=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Kirim"
        verbose_name_plural = "Kirimlar"
        ordering = ['-sana']

    def __str__(self):
        return f"{self.sana} - {self.summa} so'm ({self.xaridor.ism})"

    def save(self, *args, **kwargs):
        # USD summani hisoblash
        if self.valyuta == 'usd' and self.usd_kurs > 0:
            # USD da to'langan bo'lsa, so'mga aylantirish
            self.summa = round(Decimal(str(self.summa_usd)) * Decimal(str(self.usd_kurs)), 2)
        elif self.usd_kurs > 0:
            self.summa_usd = round(Decimal(str(self.summa)) / Decimal(str(self.usd_kurs)), 4)
        
        super().save(*args, **kwargs)
        
        # Sotuvning to'langan summasini yangilash
        self._update_sotuv_tolangan()

    def _update_sotuv_tolangan(self):
        """Sotuvning tolangan_summa va holatini yangilash"""
        sotuv = self.sotuv
        jami_tolangan = sotuv.kirimlar.aggregate(
            total=Sum('summa')
        )['total'] or Decimal('0')
        
        sotuv.tolangan_summa = jami_tolangan
        sotuv._update_tolov_holati()
        sotuv.save(update_fields=['tolangan_summa', 'tolov_holati', 'updated_at'])

    def delete(self, *args, **kwargs):
        sotuv = self.sotuv
        super().delete(*args, **kwargs)
        self._update_sotuv_tolangan.__func__(self)  # sotuv ni qayta hisoblash
        # To'g'ri usul:
        jami_tolangan = sotuv.kirimlar.aggregate(total=Sum('summa'))['total'] or Decimal('0')
        sotuv.tolangan_summa = jami_tolangan
        sotuv._update_tolov_holati()
        sotuv.save(update_fields=['tolangan_summa', 'tolov_holati', 'updated_at'])

class Feature(models.Model):
    name = models.CharField(max_length=300)
    
    def __str__(self):
        return self.name
      
class Avans(models.Model):
    
    is_active =  models.BooleanField(default=True,null=True,blank=True, verbose_name="Aktivmi")
    amount = models.PositiveIntegerField()
    ishchi =  models.ForeignKey(Ishchi,on_delete=models.PROTECT)
    created = models.DateField(default=timezone.now)    
    ended = models.DateField(null=True,blank=True,verbose_name="yopilgan sana")
    
    def __str__(self):
        return f"{self.ishchi.ism} {self.amount}"
    

class TeriSarfi(models.Model):
    """
    Kroy/Rezak ishchilari uchun teri sarfi
    Har bir ish uchun bir nechta teri sarfi bo'lishi mumkin
    """
    ish = models.ForeignKey(
        'Ish',
        on_delete=models.CASCADE,
        related_name='teri_sarflari',
        verbose_name="Ish"
    )
    ishchi = models.ForeignKey(
        'Ishchi',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='teri_sarflari',
        verbose_name="Ishchi"
    )
    xomashyo = models.ForeignKey(
        'xomashyo.Xomashyo',
        on_delete=models.PROTECT,
        related_name='teri_sarflari',
        verbose_name="Teri"
    )
    # YANGI: Variant qo'llab-quvvatlash
    variant = models.ForeignKey(
        'xomashyo.XomashyoVariant',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='teri_sarflari',
        verbose_name="Teri variant"
    )
    miqdor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Sarflangan miqdor"
    )
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")

    class Meta:
        verbose_name = "Teri sarfi"
        verbose_name_plural = "Teri sarflari"
        ordering = ['-sana']
    
    def __str__(self):
        variant_info = f" ({self.variant.rang})" if self.variant else ""
        return f"{self.ish} | {self.xomashyo.nomi}{variant_info} | {self.miqdor}"

    def save(self, *args, **kwargs):
        """
        DIQQAT: Teri sarfi faqat TeriSarfi modeliga yoziladi
        Xomashyo miqdori KAMAYTILMAYDI (bu business logic asosida)
        """
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        TeriSarfi o'chirilsa - xomashyoga qaytarish
        """
        if self.variant:
            self.variant.miqdori = F('miqdori') + self.miqdor
            self.variant.save(update_fields=['miqdori'])
        else:
            self.xomashyo.miqdori = F('miqdori') + self.miqdor
            self.xomashyo.save(update_fields=['miqdori', 'updated_at'])
        
        super().delete(*args, **kwargs)

