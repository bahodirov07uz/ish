# crm/models
from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Sum
from datetime import date
from django.utils import timezone

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
    nomi = models.CharField(max_length=255, verbose_name="Nomi")
    description = models.TextField(verbose_name="Tavsif")
    narxi = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Narxi")
    soni = models.PositiveIntegerField(verbose_name="Ombordagi soni")
    image = models.ImageField(upload_to="products/", verbose_name="Rasm",null=True,blank=True)
    avg_profit = models.PositiveIntegerField(default=0, verbose_name="O'rtacha foyda")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan sana")
    narx_kosib = models.IntegerField(default=0, verbose_name="Kasb narxi")
    narx_zakatovka = models.IntegerField(default=0, verbose_name="Zakatovka narxi")
    narx_kroy = models.IntegerField(default=0, verbose_name="Kesish narxi")
    narx_pardoz = models.IntegerField(default=0, verbose_name="Pardoza narxi")

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

    def update_total_quantity(self):
        """Mahsulotning umumiy miqdorini variantlar miqdorlari yig'indisiga moslab yangilash."""
        self.soni = self.variants.aggregate(total=models.Sum('stock'))['total'] or 0
        self.save()

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

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants", verbose_name="Mahsulot")
    size = models.CharField(max_length=10, null=True, verbose_name="O'lcham")
    color = models.CharField(max_length=50, null=True, verbose_name="Rangi")
    stock = models.PositiveIntegerField(default=0, null=True, verbose_name="Qoldiq")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, verbose_name="Narxi")
    image = models.ImageField(upload_to='product/', null=True, verbose_name="Rasm")

    class Meta:
        verbose_name = "Mahsulot varianti"
        verbose_name_plural = "Mahsulot variantlari"

    def clean(self):
        """Variant miqdorini tekshirish."""
        if self.stock > self.product.soni:
            raise ValidationError(
                f"Variant miqdori ({self.stock}) mahsulotning umumiy miqdoridan ({self.product.update_total_quantity}) oshib ketdi."
            )

    def __str__(self):
        return f"{self.product.nomi} - {self.size} - {self.color}"

    def delete(self, *args, **kwargs):
        """Variant o'chirilganda mahsulotning umumiy miqdorini yangilash."""
        super().delete(*args, **kwargs)
        self.product.update_total_quantity()

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
    ishlari = models.ForeignKey('EskiIsh', on_delete=models.CASCADE, null=True, related_name='oylik_ishlari', verbose_name="Ishlar")

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
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ishchi_profile',
        verbose_name="Foydalanuvchi"
    )
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
            ish.narxi for ish in self.ishlar.all()
        )
        return umumiy_summa

    @staticmethod
    def ishlar_soni():
        kosib_turi = Category.objects.get(nomi='kosib')
        return Ish.objects.filter(ishchi__turi=kosib_turi).aggregate(umumiy_soni=Sum('soni'))['umumiy_soni'] or 0
  
    def oy_mahsulotlar(self):
        """Joriy oyda ishchi har bir mahsulotdan qancha ishlab bergan"""
        current_month = now().month
        qs = self.ishlar.all()

        return qs.values(
            'mahsulot__nomi'
        ).annotate(
            jami_soni=Sum('soni'),
            jami_summa=Sum('narxi')
        ).order_by('mahsulot__nomi')
        
        
class Ish(models.Model):
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Mahsulot")
    soni = models.IntegerField(null=True, verbose_name="Soni")
    sana = models.DateField(null=True, auto_now_add=True, verbose_name="Sana")
    narxi = models.IntegerField(null=True, blank=True, verbose_name="Narxi")
    ishchi = models.ForeignKey(
        Ishchi, on_delete=models.CASCADE, null=True, related_name='ishlar', verbose_name="Ishchi"
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
    name = models.CharField(max_length=500, verbose_name="Nomi")
    category = models.ForeignKey(
        ChiqimTuri, related_name='chiqimlar', null=True, blank=True, on_delete=models.CASCADE, verbose_name="Kategoriya"
    )
    price = models.PositiveIntegerField(verbose_name="Narxi")
    created = models.DateField(auto_now_add=True, verbose_name="Yaratilgan sana")

    class Meta:
        verbose_name = "Chiqim"
        verbose_name_plural = "Chiqimlar"

    def __str__(self):
        return self.name

    @staticmethod
    def sum_prices():
        today = date.today()
        return Chiqim.objects.filter(
            created__year=today.year, created__month=today.month
        ).aggregate(Sum('price'))['price__sum'] or 0

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
    """Sotuvlar (xaridor mahsulot sotib olganda)"""
    xaridor = models.ForeignKey(Xaridor, on_delete=models.CASCADE, related_name="sales", verbose_name="Xaridor")
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales", verbose_name="Mahsulot")
    miqdor = models.PositiveIntegerField(verbose_name="Miqdor")
    umumiy_summa = models.DecimalField(max_digits=12, decimal_places=2, editable=False, verbose_name="Umumiy summa")
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")

    class Meta:
        verbose_name = "Sotuv"
        verbose_name_plural = "Sotuvlar"

    def save(self, *args, **kwargs):
        # Avtomatik umumiy summani hisoblash
        self.umumiy_summa = self.mahsulot.narxi * self.miqdor
        super().save(*args, **kwargs)

        # ✅ Mahsulot sonini kamaytirish
        self.mahsulot.soni = max(0, self.mahsulot.soni - self.miqdor)
        self.mahsulot.save()

        # ✅ Shu sotuv uchun kirim yozuvi yaratish (agar mavjud bo'lmasa)
        Kirim.objects.get_or_create(
            sotuv=self,
            defaults={
                "xaridor": self.xaridor,
                "mahsulot": self.mahsulot,
                "summa": self.umumiy_summa,
                "sana": self.sana,
            },
        )

    def __str__(self):
        return f"{self.xaridor.ism} - {self.mahsulot.nomi} ({self.miqdor} ta)"

class Kirim(models.Model):
    """Avtomatik yaratiladigan kirim yozuvi"""
    sotuv = models.OneToOneField(Sotuv, on_delete=models.CASCADE, related_name="kirim", verbose_name="Sotuv")
    xaridor = models.ForeignKey(Xaridor, on_delete=models.CASCADE, verbose_name="Xaridor")
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Mahsulot")
    summa = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Summa")
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")

    class Meta:
        verbose_name = "Kirim"
        verbose_name_plural = "Kirimlar"

    def __str__(self):
        return f"{self.mahsulot.nomi} - {self.summa} so'm ({self.xaridor.ism})"