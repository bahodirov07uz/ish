from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Sum
from datetime import date
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    STATUS_CHOICES = [
        ('new', 'New'),
        ('bestseller', 'Bestseller'),
        ('sale', 'Sale'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products", null=True)
    nomi = models.CharField(max_length=255)
    description = models.TextField()
    narxi = models.DecimalField(max_digits=10, decimal_places=2)
    soni = models.PositiveIntegerField()  # Omborda qancha bor
    image = models.ImageField(upload_to="products/")
    avg_profit = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    narx_kosib = models.IntegerField(default=0)
    narx_zakatovka = models.IntegerField(default=0)
    narx_kroy = models.IntegerField(default=0)
    narx_pardoz = models.IntegerField(default=0)

    def update_total_quantity(self):
        """Mahsulotning umumiy miqdorini variantlar miqdorlari yig‘indisiga moslab yangilash."""
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
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=10,null=True)  
    color = models.CharField(max_length=50,null=True)  
    stock = models.PositiveIntegerField(default=0,null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    image = models.ImageField(upload_to='product/',null=True)


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
    
    
# ishchilar

class IshchiCategory(models.Model):
    nomi = models.CharField(max_length=50)

    def __str__(self):
        return self.nomi

class Oyliklar(models.Model):
    sana = models.DateField(default=now)
    ishchi = models.ForeignKey(
        'Ishchi', on_delete=models.CASCADE, related_name='oyliklar'
    )
    oylik = models.IntegerField(null=True)
    yopilgan = models.BooleanField(default=False)
    ishlari = models.ForeignKey('EskiIsh', on_delete=models.CASCADE, null=True, related_name='oylik_ishlari')

    def __str__(self):
        return f"{self.ishchi.ism} - {self.sana} - {self.oylik}"

class Ishchi(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='ishchi_profile'
    )
    ism = models.CharField(max_length=50)
    familiya = models.CharField(max_length=50)
    maosh = models.IntegerField()
    telefon = models.CharField(max_length=15)  # O'zgartirilgan
    turi = models.ForeignKey(IshchiCategory, on_delete=models.CASCADE, null=True, related_name='ish_turi')
    is_oylik_open = models.BooleanField(default=True, null=True)
    yangi_oylik = models.IntegerField(default=0, null=True)
    oylik_yopilgan_sana = models.DateField(auto_now=True, null=True)
    current_oylik = models.OneToOneField(
        Oyliklar, on_delete=models.SET_NULL, null=True, blank=True, related_name="current_ishchi"
    )
    is_active = models.BooleanField(default=True)
    eski_ishlar = models.ForeignKey('EskiIsh', on_delete=models.CASCADE, related_name='ishchilar', null=True, blank=True)

    def __str__(self):
        return f"{self.ism} {self.familiya}"

    def umumiy_oylik(self):
        umumiy_summa = sum(
            ish.narxi for ish in self.ishlar.filter(sana__month=now().month)
        )
        return umumiy_summa

    @staticmethod
    def ishlar_soni():
        kosib_turi = Category.objects.get(nomi='kosib')
        return Ish.objects.filter(ishchi__turi=kosib_turi).aggregate(umumiy_soni=Sum('soni'))['umumiy_soni'] or 0

class EskiIsh(models.Model):
    ishchi = models.ForeignKey(Ishchi, on_delete=models.CASCADE, null=True)
    mahsulot = models.CharField(max_length=500, null=True)
    sana = models.DateField(null=True)
    narxi = models.IntegerField(null=True)
    soni = models.IntegerField(null=True)
    ishchi_oylik = models.ForeignKey(
        Oyliklar, on_delete=models.CASCADE, null=True, related_name='eski_ishlar'
    )

class Ish(models.Model):
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE)
    soni = models.IntegerField(null=True)
    sana = models.DateField(null=True, auto_now_add=True)
    narxi = models.IntegerField(null=True, blank=True)
    ishchi = models.ForeignKey(
        Ishchi, on_delete=models.CASCADE, null=True, related_name='ishlar'
    )

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
    name = models.CharField(max_length=200)
    def __str__(self):
        return self.name

class Chiqim(models.Model):
    name = models.CharField(max_length=500)
    category = models.ForeignKey(
        ChiqimTuri, related_name='chiqimlar', null=True, blank=True, on_delete=models.CASCADE
    )
    price = models.PositiveIntegerField()
    created = models.DateField(auto_now_add=True)

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
    ism = models.CharField(max_length=150)
    telefon = models.CharField(max_length=20, blank=True, null=True)
    manzil = models.CharField(max_length=255, blank=True, null=True)
    izoh = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ism
    
class Sotuv(models.Model):
    """Sotuvlar (xaridor mahsulot sotib olganda)"""
    xaridor = models.ForeignKey(Xaridor, on_delete=models.CASCADE, related_name="sales")
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="sales")
    miqdor = models.PositiveIntegerField()
    umumiy_summa = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    sana = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Avtomatik umumiy summani hisoblash
        self.umumiy_summa = self.mahsulot.narxi * self.miqdor
        super().save(*args, **kwargs)

        # ✅ Mahsulot sonini kamaytirish
        self.mahsulot.soni = max(0, self.mahsulot.soni - self.miqdor)
        self.mahsulot.save()

        # ✅ Shu sotuv uchun kirim yozuvi yaratish (agar mavjud bo‘lmasa)
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
    sotuv = models.OneToOneField(Sotuv, on_delete=models.CASCADE, related_name="kirim")
    xaridor = models.ForeignKey(Xaridor, on_delete=models.CASCADE)
    mahsulot = models.ForeignKey(Product, on_delete=models.CASCADE)
    summa = models.DecimalField(max_digits=12, decimal_places=2)
    sana = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.mahsulot.nomi} - {self.summa} so'm ({self.xaridor.ism})"
    
    