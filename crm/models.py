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
        verbose_name = "Ishchi"
        verbose_name_plural = "Ishchilar"

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
    sana = models.DateField(null=True, auto_now_add=True, verbose_name="Sana")
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
            elif self.ishchi.turi.nomi == "pardozchi":
                self.narxi = self.mahsulot.narx_pardoz * int(self.soni)
            elif self.ishchi.turi == "rezak":
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

class Chiqim(models.Model):
    name         = models.CharField(max_length=500, verbose_name="Nomi")
    category     = models.ForeignKey(
        ChiqimTuri, related_name='chiqimlar',
        null=True, blank=True, on_delete=models.SET_NULL,
        verbose_name="Kategoriya"
    )
    price        = models.DecimalField(
        max_digits=20, decimal_places=2,
        verbose_name="Jami narxi"
    )
    izoh         = models.TextField(blank=True, verbose_name="Izoh")
    created      = models.DateField(auto_now_add=True, verbose_name="Yaratilgan sana")
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Yaratuvchi"
    )

    class Meta:
        verbose_name = "Chiqim"
        verbose_name_plural = "Chiqimlar"
        ordering = ['-created']

    def __str__(self):
        return self.name

    @staticmethod
    def sum_prices():
        today = date.today()
        return Chiqim.objects.filter(
            created__year=today.year,
            created__month=today.month
        ).aggregate(Sum('price'))['price__sum'] or 0


class ChiqimItem(models.Model):

    ITEM_TURI = [
        ('xomashyo', 'Xomashyo'),
        ('boshqa',   'Boshqa chiqim'),
    ]

    chiqim              = models.ForeignKey(
        Chiqim, on_delete=models.CASCADE,
        related_name='itemlar', verbose_name="Chiqim"
    )
    item_turi           = models.CharField(
        max_length=20, choices=ITEM_TURI,
        default='boshqa', verbose_name="Turi"
    )

    # ── Umumiy ──────────────────────────────────────────────────
    name                = models.CharField(max_length=500, verbose_name="Nomi")
    price               = models.DecimalField(
        max_digits=20, decimal_places=2, verbose_name="Narxi"
    )

    # ── Faqat xomashyo uchun ────────────────────────────────────
    xomashyo  = models.ForeignKey(
        Xomashyo, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Xomashyo"
    )
    miqdor              = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True, verbose_name="Miqdori"
    )
    yetkazib_beruvchi   = models.ForeignKey(
        YetkazibBeruvchi, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Yetkazib beruvchi"
    )

    # ── Bog'liq XomashyoHarakat (avtomatik to'ldiriladi) ────────
    harakat             = models.OneToOneField(
        XomashyoHarakat, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='chiqim_item',
        verbose_name="Bog'liq harakat"
    )

    class Meta:
        verbose_name = "Chiqim qatori"
        verbose_name_plural = "Chiqim qatorlari"

    def __str__(self):
        return f"{self.name} — {self.price} so'm"

    def save(self, *args, **kwargs):
        """
        Yangi xomashyo qatori saqlanganда XomashyoHarakat avtomatik yaratiladi.
        """
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new and self.item_turi == 'xomashyo' and self.xomashyo and self.harakat is None:
            harakat = XomashyoHarakat.objects.create(
                xomashyo=self.xomashyo,
                harakat_turi='kirim',
                miqdori=self.miqdor,
                narxi=self.price,
                izoh=self.chiqim.izoh or f"{self.xomashyo.nomi} sotib olindi",
                yetkazib_beruvchi=self.yetkazib_beruvchi,
                foydalanuvchi=self.chiqim.created_by,
            )
            # harakat.save() ichida stok yangilanadi (XomashyoHarakat.save logikasi)
            ChiqimItem.objects.filter(pk=self.pk).update(harakat=harakat)
            self.harakat = harakat
            
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
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Jami summa"
    )
    chegirma = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Chegirma"
    )
    yakuniy_summa = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        verbose_name="Yakuniy summa"
    )
    tolov_holati = models.CharField(
        max_length=20,
        choices=[
            ('tolandi', 'To\'landi'),
            ('qisman', 'Qisman to\'landi'),
            ('tolanmadi', 'To\'lanmadi'),
        ],
        default='tolandi',
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

    def update_summa(self):
        """Sotuv ichidagi barcha itemlarni hisoblash"""
        self.jami_summa = self.items.aggregate(
            total=Sum(F('narx') * F('miqdor'))
        )['total'] or 0
        self.yakuniy_summa = self.jami_summa - self.chegirma
        self.save(update_fields=['jami_summa', 'yakuniy_summa', 'updated_at'])

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Yangi sotuv uchun kirim yaratish
        if is_new:
            from .models import Kirim  # Circular import oldini olish
            Kirim.objects.create(
                sotuv=self,
                xaridor=self.xaridor,
                summa=self.yakuniy_summa,
                sana=self.sana,
                izoh=f"Sotuv #{self.id}"
            )


class SotuvItem(models.Model):
    """Sotuv tarkibidagi alohida mahsulot"""
    sotuv = models.ForeignKey(
        Sotuv, 
        on_delete=models.CASCADE, 
        related_name="items", 
        verbose_name="Sotuv"
    )
    mahsulot = models.ForeignKey(
        'Product', 
        on_delete=models.PROTECT, 
        related_name="sotuv_items", 
        verbose_name="Mahsulot"
    )
    variant = models.ForeignKey(
        'ProductVariant',
        on_delete=models.PROTECT,
        related_name="sotuv_items",
        verbose_name="Variant"
    )
    miqdor = models.PositiveIntegerField(verbose_name="Miqdor")
    narx = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Birlik narxi"
    )
    jami = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        editable=False,
        verbose_name="Jami summa"
    )
    izoh = models.CharField(max_length=255, blank=True, null=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Sotuv elementi"
        verbose_name_plural = "Sotuv elementlari"

    def __str__(self):
        return f"{self.variant} - {self.miqdor} ta - {self.narx} so'm"

    def save(self, *args, **kwargs):
        # 1. Jami summasini hisoblash
        self.jami = Decimal(str(self.narx)) * Decimal(str(self.miqdor))
        
        # 2. Yangi item ekanligini tekshirish
        is_new = self.pk is None
        old_miqdor = 0
        
        if not is_new:
            # Eski miqdorni olish (stockni qaytarish uchun)
            old_item = SotuvItem.objects.get(pk=self.pk)
            old_miqdor = old_item.miqdor
        
        # 3. Stockni tekshirish
        if is_new:
            # Yangi item uchun
            if self.variant.stock < self.miqdor:
                raise ValueError(
                    f"Omborda yetarli {self.variant} yo'q! "
                    f"Mavjud: {self.variant.stock} ta, Kerak: {self.miqdor} ta"
                )
        else:
            # Tahrirlash uchun
            miqdor_farqi = self.miqdor - old_miqdor
            if miqdor_farqi > 0:  # Miqdor oshgan
                if self.variant.stock < miqdor_farqi:
                    raise ValueError(
                        f"Omborda yetarli {self.variant} yo'q! "
                        f"Mavjud: {self.variant.stock} ta"
                    )
        
        # 4. Bazaga saqlash
        super().save(*args, **kwargs)
        
        # 5. Stockni yangilash
        from django.db import transaction
        
        with transaction.atomic():
            self.variant.refresh_from_db()
            
            if is_new:
                # Yangi item - stockni kamaytirish
                self.variant.stock = F('stock') - self.miqdor
            else:
                # Tahrirlash - farqni hisoblash
                miqdor_farqi = self.miqdor - old_miqdor
                if miqdor_farqi > 0:
                    self.variant.stock = F('stock') - miqdor_farqi
                elif miqdor_farqi < 0:
                    self.variant.stock = F('stock') + abs(miqdor_farqi)
            
            self.variant.save()
            self.variant.refresh_from_db()
        
        # 6. Mahsulot umumiy miqdorini yangilash
        self.mahsulot.update_total_quantity()
        
        # 7. Sotuvning umumiy summasini yangilash
        self.sotuv.update_summa()

    def delete(self, *args, **kwargs):
        """Item o'chirilganda stockni qaytarish"""
        from django.db import transaction
        
        with transaction.atomic():
            # Stockni qaytarish
            self.variant.stock = F('stock') + self.miqdor
            self.variant.save()
            self.variant.refresh_from_db()
            
            # Mahsulot umumiy miqdorini yangilash
            self.mahsulot.update_total_quantity()
            
            # Sotuvni saqlash
            sotuv = self.sotuv
            
            # Itemni o'chirish
            super().delete(*args, **kwargs)
            
            # Sotuv summasini yangilash
            sotuv.update_summa()

class Kirim(models.Model):
    
    """Avtomatik yaratiladigan kirim yozuvi"""
    sotuv = models.OneToOneField(Sotuv, on_delete=models.CASCADE, related_name="kirim", verbose_name="Sotuv")
    xaridor = models.ForeignKey(Xaridor, on_delete=models.CASCADE, verbose_name="Xaridor")
    summa = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Summa")
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    izoh = models.TextField(null=True,blank=True)
    class Meta:
        verbose_name = "Kirim"
        verbose_name_plural = "Kirimlar"

    def __str__(self):
        return f"{self.sana} - {self.summa} so'm ({self.xaridor.ism})"

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

class testmodel(models.Model):
    name =  models.CharField(max_length=2)