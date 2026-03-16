# budget/models.py
from django.db import models
from django.utils import timezone
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.conf import settings


class Tranzaksiya(models.Model):
    """
    Har bir pul chiqimi uchun avtomatik log.
    Chiqim.save() va XomashyoHarakat.save() orqali signal bilan yaratiladi.
    Qo'lda yaratilmaydi.
    """
    MANBA = [
        ('chiqim',    'Chiqim'),
        ('xomashyo',  'Xomashyo xaridi'),
    ]

    # Manba
    manba           = models.CharField(max_length=20, choices=MANBA, verbose_name="Manba")
    chiqim          = models.OneToOneField(
        'crm.Chiqim', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tranzaksiya',
        verbose_name="Chiqim"
    )
    xomashyo_harakat = models.OneToOneField(
        'xomashyo.XomashyoHarakat', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tranzaksiya',
        verbose_name="Xomashyo harakati"
    )

    # Kim amalga oshirdi
    ishchi          = models.ForeignKey(
        'crm.Ishchi', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tranzaksiyalar',
        verbose_name="Ishchi"
    )
    foydalanuvchi   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Foydalanuvchi"
    )

    # Summa
    summa_uzs       = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    summa_usd       = models.DecimalField(max_digits=20, decimal_places=4, default=0, null=True, blank=True)

    # Tavsif (manba modeldan ko'chiriladi)
    nomi            = models.CharField(max_length=500, verbose_name="Nomi/Tavsif")
    kategoriya      = models.CharField(max_length=200, blank=True, verbose_name="Kategoriya")

    sana            = models.DateField(verbose_name="Sana")
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
        ordering            = ['-sana', '-created_at']

    def __str__(self):
        return f"{self.sana} | {self.nomi} | {self.summa_uzs:,.0f} so'm"


class Byudjet(models.Model):
    """
    Davr uchun pul limiti.
    Sarflar Tranzaksiya modelidan avtomatik hisoblanadi.
    """
    nomi            = models.CharField(max_length=255)
    davr_boshi      = models.DateField()
    davr_oxiri      = models.DateField()
    umumiy_summa    = models.DecimalField(max_digits=20, decimal_places=2)
    izoh            = models.TextField(blank=True)
    yaratgan        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Byudjet"
        verbose_name_plural = "Byudjetlar"
        ordering            = ['-davr_boshi']

    def __str__(self):
        return f"{self.nomi} ({self.davr_boshi} – {self.davr_oxiri})"

    # ── Hisoblangan xususiyatlar ──────────────────────────────────

    def _tranzaksiyalar(self):
        return Tranzaksiya.objects.filter(
            sana__gte=self.davr_boshi,
            sana__lte=self.davr_oxiri,
        )

    @property
    def jami_sarfi(self) -> Decimal:
        return self._tranzaksiyalar().aggregate(
            s=Coalesce(Sum('summa_uzs'), Value(Decimal('0')))
        )['s']

    @property
    def chiqim_sarfi(self) -> Decimal:
        return self._tranzaksiyalar().filter(manba='chiqim').aggregate(
            s=Coalesce(Sum('summa_uzs'), Value(Decimal('0')))
        )['s']

    @property
    def xomashyo_sarfi(self) -> Decimal:
        return self._tranzaksiyalar().filter(manba='xomashyo').aggregate(
            s=Coalesce(Sum('summa_uzs'), Value(Decimal('0')))
        )['s']

    @property
    def qoldiq(self) -> Decimal:
        return max(self.umumiy_summa - self.jami_sarfi, Decimal('0'))

    @property
    def sarfi_foiz(self) -> float:
        if self.umumiy_summa > 0:
            return min(round(float(self.jami_sarfi / self.umumiy_summa * 100), 1), 100)
        return 0.0

    @property
    def holat(self) -> str:
        f = self.sarfi_foiz
        if f >= 100: return 'oshib_ketdi'
        if f >= 90:  return 'xavfli'
        if f >= 75:  return 'ogoh'
        return 'xavfsiz'

    @property
    def is_active(self) -> bool:
        today = timezone.now().date()
        return self.davr_boshi <= today <= self.davr_oxiri

    def sarflar_by_kategoriya(self):
        return (
            self._tranzaksiyalar()
            .values('kategoriya', 'manba')
            .annotate(jami=Sum('summa_uzs'))
            .order_by('-jami')
        )

    def sarflar_by_ishchi(self):
        return (
            self._tranzaksiyalar()
            .filter(ishchi__isnull=False)
            .values('ishchi__id', 'ishchi__ism', 'ishchi__familiya')
            .annotate(jami=Sum('summa_uzs'))
            .order_by('-jami')
        )


class ByudjetLimit(models.Model):
    """Kategoriya yoki manba bo'yicha limit — ixtiyoriy."""
    byudjet         = models.ForeignKey(Byudjet, on_delete=models.CASCADE, related_name='limitlar')
    nomi            = models.CharField(max_length=200, verbose_name="Limit nomi")
    # Filtr: manba va/yoki kategoriya nomi bo'yicha
    manba           = models.CharField(
        max_length=20, blank=True,
        choices=[('chiqim', 'Chiqim'), ('xomashyo', 'Xomashyo'), ('', 'Barchasi')],
        default=''
    )
    kategoriya      = models.CharField(max_length=200, blank=True, help_text="Bo'sh = barcha kategoriyalar")
    limit_summa     = models.DecimalField(max_digits=20, decimal_places=2)

    class Meta:
        verbose_name = "Byudjet limiti"

    def __str__(self):
        return f"{self.byudjet} → {self.nomi}: {self.limit_summa:,.0f}"

    def _qs(self):
        qs = Tranzaksiya.objects.filter(
            sana__gte=self.byudjet.davr_boshi,
            sana__lte=self.byudjet.davr_oxiri,
        )
        if self.manba:
            qs = qs.filter(manba=self.manba)
        if self.kategoriya:
            qs = qs.filter(kategoriya=self.kategoriya)
        return qs

    @property
    def haqiqiy_sarfi(self) -> Decimal:
        return self._qs().aggregate(
            s=Coalesce(Sum('summa_uzs'), Value(Decimal('0')))
        )['s']

    @property
    def foiz(self) -> float:
        if self.limit_summa > 0:
            return min(round(float(self.haqiqiy_sarfi / self.limit_summa * 100), 1), 100)
        return 0.0

    @property
    def holat(self) -> str:
        f = self.foiz
        if f >= 100: return 'oshib_ketdi'
        if f >= 90:  return 'xavfli'
        if f >= 75:  return 'ogoh'
        return 'xavfsiz'