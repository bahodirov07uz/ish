from django.db import models
from django.db.models import Sum, F
from django.utils import timezone
from decimal import Decimal


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

    # USD kurs (qo'lda kiritiladi)
    usd_kurs = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="USD kursi (sotuv paytida)",
        help_text="Qo'lda kiritiladigan USD kursi"
    )
    jami_summa_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Jami summa (USD)"
    )
    yakuniy_summa_usd = models.DecimalField(
        max_digits=12, decimal_places=4, default=0,
        verbose_name="Yakuniy summa (USD)"
    )

    # To'langan summa (qarz tizimi uchun)
    tolangan_summa = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name="To'langan summa (so'm)"
    )

    tolov_holati = models.CharField(
        max_length=20,
        choices=[
            ('tolandi', "To'landi"),
            ('qisman', "Qisman to'landi"),
            ('tolanmadi', "To'lanmadi"),
        ],
        # CHANGE 2: default tolanmadi
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
        return max(self.yakuniy_summa - self.tolangan_summa, Decimal('0'))

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
        )['total'] or Decimal('0')
        self.yakuniy_summa = self.jami_summa - self.chegirma

        if self.usd_kurs and self.usd_kurs > 0:
            self.jami_summa_usd = round(
                Decimal(str(self.jami_summa)) / Decimal(str(self.usd_kurs)), 4
            )
            self.yakuniy_summa_usd = round(
                Decimal(str(self.yakuniy_summa)) / Decimal(str(self.usd_kurs)), 4
            )

        self._update_tolov_holati()

        self.save(update_fields=[
            'jami_summa', 'yakuniy_summa', 'jami_summa_usd',
            'yakuniy_summa_usd', 'tolov_holati', 'updated_at'
        ])

    def _update_tolov_holati(self):
        """To'langan summaga qarab holatni avtomatik yangilash"""
        if self.tolangan_summa >= self.yakuniy_summa and self.yakuniy_summa > 0:
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
    narx_usd = models.DecimalField(
        max_digits=10, decimal_places=4, default=0,
        verbose_name="Birlik narxi (USD)"
    )
    narx_turi = models.CharField(
        max_length=3,
        choices=[('uzs', "So'm"), ('usd', 'USD')],
        default='uzs',
        verbose_name="Narx valyutasi"
    )
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
        from django.db import transaction

        usd_kurs = Decimal(str(self.sotuv.usd_kurs)) if self.sotuv.usd_kurs else Decimal('0')

        is_new = self.pk is None
        old_miqdor = 0

        if not is_new:
            old_item = SotuvItem.objects.get(pk=self.pk)
            old_miqdor = old_item.miqdor
            self.narx_turi = old_item.narx_turi

            if self.narx != old_item.narx and usd_kurs > 0:
                self.narx_usd = round(Decimal(str(self.narx)) / usd_kurs, 4)
            else:
                self.narx_usd = old_item.narx_usd

        if is_new:
            if self.narx_turi == 'usd' and usd_kurs > 0:
                self.narx_usd = Decimal(str(self.narx))
                self.narx = round(self.narx_usd * usd_kurs, 2)
                self.narx_turi = 'uzs'
            elif usd_kurs > 0:
                self.narx_usd = round(Decimal(str(self.narx)) / usd_kurs, 4)

        self.jami = Decimal(str(self.narx)) * Decimal(str(self.miqdor))
        if usd_kurs > 0:
            self.jami_usd = round(self.jami / usd_kurs, 4)
        else:
            self.jami_usd = Decimal('0')

        # Stock tekshirish
        if is_new:
            if self.variant.stock < self.miqdor:
                raise ValueError(
                    f"Omborda yetarli {self.variant} yo'q! "
                    f"Mavjud: {self.variant.stock} ta, Kerak: {self.miqdor} ta"
                )
        else:
            miqdor_farqi = self.miqdor - old_miqdor
            if miqdor_farqi > 0 and self.variant.stock < miqdor_farqi:
                raise ValueError(
                    f"Omborda yetarli {self.variant} yo'q! "
                    f"Mavjud: {self.variant.stock} ta"
                )

        super().save(*args, **kwargs)

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


# CHANGE 4: Qaytarish modeli
class Qaytarish(models.Model):
    """Sotuv ichidan mahsulot qaytarish"""
    sotuv = models.ForeignKey(
        Sotuv, on_delete=models.CASCADE,
        related_name="qaytarishlar", verbose_name="Sotuv"
    )
    sotuv_item = models.ForeignKey(
        SotuvItem, on_delete=models.CASCADE,
        related_name="qaytarishlar", verbose_name="Sotuv elementi"
    )
    miqdor = models.PositiveIntegerField(verbose_name="Qaytarilgan miqdor")
    sabab = models.CharField(
        max_length=255, blank=True, null=True,
        verbose_name="Qaytarish sababi"
    )
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Qaytarish"
        verbose_name_plural = "Qaytarishlar"
        ordering = ['-sana']

    def __str__(self):
        return f"Qaytarish #{self.id} - {self.sotuv_item.variant} - {self.miqdor} ta"

    @property
    def summa(self):
        """Qaytarilgan summa"""
        return self.miqdor * self.sotuv_item.narx

    def save(self, *args, **kwargs):
        from django.db import transaction

        is_new = self.pk is None

        if is_new:
            # Necha ta qaytarish mumkinligini tekshirish
            already_returned = self.sotuv_item.qaytarishlar.aggregate(
                total=Sum('miqdor')
            )['total'] or 0
            max_returnable = self.sotuv_item.miqdor - already_returned

            if self.miqdor > max_returnable:
                raise ValueError(
                    f"Qaytarish miqdori ({self.miqdor}) "
                    f"ruxsat etilganidan ({max_returnable}) ko'p!"
                )

            with transaction.atomic():
                super().save(*args, **kwargs)

                # Stockni qaytarish
                variant = self.sotuv_item.variant
                variant.stock = F('stock') + self.miqdor
                variant.save()
                variant.refresh_from_db()

                self.sotuv_item.mahsulot.update_total_quantity()

                # Sotuvning jami miqdorini yangilash (SotuvItem.miqdor kamaytirilmaydi,
                # faqat qaytarish yozuvi qoladi — bu auditor mantig'i)
                # Agar sotuv summasini ham kamaytirmoqchi bo'lsangiz,
                # quyidagi qatorni uncomment qiling:
                # self.sotuv.update_summa()
        else:
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            variant = self.sotuv_item.variant
            variant.stock = F('stock') - self.miqdor
            variant.save()
            variant.refresh_from_db()
            self.sotuv_item.mahsulot.update_total_quantity()
            super().delete(*args, **kwargs)


class Kirim(models.Model):
    """Sotuv to'lovlari (bir sotuv uchun bir nechta to'lov bo'lishi mumkin)"""
    sotuv = models.ForeignKey(
        Sotuv, on_delete=models.CASCADE,
        related_name="kirimlar",
        verbose_name="Sotuv",
        null=True, blank=True
    )
    xaridor = models.ForeignKey(
        Xaridor, on_delete=models.CASCADE, verbose_name="Xaridor"
    )
    summa = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name="Summa (so'm)"
    )
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
    sana = models.DateTimeField(default=timezone.now, verbose_name="Sana")
    izoh = models.TextField(null=True, blank=True, verbose_name="Izoh")

    class Meta:
        verbose_name = "Kirim"
        verbose_name_plural = "Kirimlar"
        ordering = ['-sana']

    def __str__(self):
        return f"{self.sana} - {self.summa} so'm ({self.xaridor.ism})"

    def save(self, *args, **kwargs):
        if self.valyuta == 'usd' and self.usd_kurs > 0:
            self.summa = round(
                Decimal(str(self.summa_usd)) * Decimal(str(self.usd_kurs)), 2
            )
        elif self.usd_kurs > 0:
            self.summa_usd = round(
                Decimal(str(self.summa)) / Decimal(str(self.usd_kurs)), 4
            )

        super().save(*args, **kwargs)
        self._update_sotuv_tolangan()

    def _update_sotuv_tolangan(self):
        """Sotuvning tolangan_summa va holatini yangilash"""
        if not self.sotuv:
            return
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
        if sotuv:
            jami_tolangan = sotuv.kirimlar.aggregate(
                total=Sum('summa')
            )['total'] or Decimal('0')
            sotuv.tolangan_summa = jami_tolangan
            sotuv._update_tolov_holati()
            sotuv.save(update_fields=['tolangan_summa', 'tolov_holati', 'updated_at'])