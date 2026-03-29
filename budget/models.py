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
        ('chiqim',   'Chiqim'),
        ('xomashyo', 'Xomashyo xaridi'),
    ]

    manba = models.CharField(max_length=20, choices=MANBA, verbose_name="Manba")
    chiqim = models.OneToOneField(
        'crm.Chiqim', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tranzaksiya',
        verbose_name="Chiqim"
    )
    xomashyo_harakat = models.OneToOneField(
        'xomashyo.XomashyoHarakat', on_delete=models.CASCADE,
        null=True, blank=True, related_name='tranzaksiya',
        verbose_name="Xomashyo harakati"
    )

    ishchi = models.ForeignKey(
        'crm.Ishchi', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tranzaksiyalar',
        verbose_name="Ishchi"
    )
    foydalanuvchi = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name="Foydalanuvchi"
    )

    summa_uzs = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    summa_usd = models.DecimalField(max_digits=20, decimal_places=4, default=0, null=True, blank=True)

    nomi      = models.CharField(max_length=500, verbose_name="Nomi/Tavsif")
    kategoriya = models.CharField(max_length=200, blank=True, verbose_name="Kategoriya")

    sana       = models.DateField(verbose_name="Sana",default=timezone.now())
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
        ordering            = ['-sana', '-created_at']
        indexes = [
            models.Index(fields=['sana']),
            models.Index(fields=['manba']),
            models.Index(fields=['kategoriya']),
        ]

    def __str__(self):
        return f"{self.sana} | {self.nomi} | {self.summa_uzs:,.0f} so'm"


class Byudjet(models.Model):
    """
    Davr uchun pul limiti.
    Sarflar Tranzaksiya modelidan avtomatik hisoblanadi.
    """
    nomi         = models.CharField(max_length=255)
    davr_boshi   = models.DateField()
    davr_oxiri   = models.DateField()
    umumiy_summa = models.DecimalField(max_digits=20, decimal_places=2)
    izoh         = models.TextField(blank=True)
    yaratgan     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Byudjet"
        verbose_name_plural = "Byudjetlar"
        ordering            = ['-davr_boshi']

    def __str__(self):
        return f"{self.nomi} ({self.davr_boshi} – {self.davr_oxiri})"

    def _tranzaksiyalar(self):
        """Byudjet davriga tegishli barcha tranzaksiyalar."""
        return Tranzaksiya.objects.filter(
            sana__gte=self.davr_boshi,
            sana__lte=self.davr_oxiri,
        )

    # ── Aggregat xususiyatlar (har biri bitta DB query) ──────────

    def get_sarflar(self) -> dict:
        """
        Barcha summalarni BITTA query bilan qaytaradi.
        Natija: {'jami': Decimal, 'chiqim': Decimal, 'xomashyo': Decimal}
        """
        from django.db.models import Case, When, DecimalField

        result = self._tranzaksiyalar().aggregate(
            jami=Coalesce(Sum('summa_uzs'), Value(Decimal('0')), output_field=DecimalField()),
            chiqim=Coalesce(
                Sum('summa_uzs', filter=models.Q(manba='chiqim')),
                Value(Decimal('0')), output_field=DecimalField()
            ),
            xomashyo=Coalesce(
                Sum('summa_uzs', filter=models.Q(manba='xomashyo')),
                Value(Decimal('0')), output_field=DecimalField()
            ),
        )
        return result

    @property
    def jami_sarfi(self) -> Decimal:
        return self.get_sarflar()['jami']

    @property
    def chiqim_sarfi(self) -> Decimal:
        return self.get_sarflar()['chiqim']

    @property
    def xomashyo_sarfi(self) -> Decimal:
        return self.get_sarflar()['xomashyo']

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
    """
    Byudjet ichidagi kategoriya/manba bo'yicha limit.
    haqiqiy_sarfi Tranzaksiyadan hisoblanadi.
    """
    MANBA = [
        ('chiqim',   'Chiqim'),
        ('xomashyo', 'Xomashyo xaridi'),
        ('',         'Hammasi'),
    ]

    byudjet     = models.ForeignKey(Byudjet, on_delete=models.CASCADE, related_name='limitlar')
    nomi        = models.CharField(max_length=255, verbose_name="Limit nomi")
    manba       = models.CharField(max_length=20, choices=MANBA, blank=True, verbose_name="Manba filtri")
    kategoriya  = models.CharField(max_length=200, blank=True, verbose_name="Kategoriya filtri")
    limit_summa = models.DecimalField(max_digits=20, decimal_places=2, verbose_name="Limit (so'm)")
    created_at  = models.DateTimeField(default=timezone.now())

    class Meta:
        verbose_name        = "Byudjet limiti"
        verbose_name_plural = "Byudjet limitlari"
        ordering            = ['-limit_summa']

    def __str__(self):
        return f"{self.byudjet.nomi} — {self.nomi}: {self.limit_summa:,.0f}"

    def _tranzaksiyalar(self):
        """Limit shartlariga mos tranzaksiyalar."""
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
        return self._tranzaksiyalar().aggregate(
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

    @property
    def qoldiq(self) -> Decimal:
        return max(self.limit_summa - self.haqiqiy_sarfi, Decimal('0'))