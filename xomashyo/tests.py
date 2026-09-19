import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from xomashyo.models import Xomashyo, XomashyoCategory, XomashyoHarakat, YetkazibBeruvchi
from crm.models import Chiqim, ChiqimItem
from budget.models import Tranzaksiya

User = get_user_model()


class XomashyoKirimTolovTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='staffuser',
            password='password123',
            is_staff=True
        )
        self.client.login(username='staffuser', password='password123')

        self.category = XomashyoCategory.objects.create(
            name="Asosiy materiallar",
            turi='real'
        )
        self.yb = YetkazibBeruvchi.objects.create(
            nomi="MChJ Yetkazuvchi",
            telefon="+998901234567",
            manzil="Toshkent"
        )
        self.xomashyo1 = Xomashyo.objects.create(
            nomi="Mato",
            category=self.category,
            miqdori=Decimal('10'),
            olchov_birligi='kg',
            narxi=Decimal('50000'),
            yetkazib_beruvchi=self.yb
        )
        self.xomashyo2 = Xomashyo.objects.create(
            nomi="Tugma",
            category=self.category,
            miqdori=Decimal('100'),
            olchov_birligi='dona',
            narxi=Decimal('1000'),
            yetkazib_beruvchi=self.yb
        )

    def test_tolanmagan_kirim(self):
        """To'lanmagan kirim: Chiqim ham, Tranzaksiya ham yaratilmaydi."""
        initial_stock = self.xomashyo1.miqdori
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 5,
            'birlik_narx_uzs': 50000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'tolov_rejim': 'tolanmagan',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        self.xomashyo1.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, initial_stock + 5)

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1).first()
        self.assertIsNotNone(harakat)
        self.assertEqual(harakat.tolov_holati, 'tolanmagan')
        self.assertEqual(harakat.tolangan_uzs, Decimal('0'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('250000'))

        self.assertEqual(Chiqim.objects.count(), 0)
        self.assertEqual(Tranzaksiya.objects.count(), 0)

    def test_toliq_tolov_kirim(self):
        """To'liq to'lovli kirim: holat 'toliq', qoldiq 0, Chiqim + ChiqimItem + Tranzaksiya bittadan."""
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 4,
            'birlik_narx_uzs': 50000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'usd_kurs': '12500',
            'tolov_rejim': 'toliq',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1).first()
        self.assertEqual(harakat.tolov_holati, 'toliq')
        self.assertEqual(harakat.tolangan_uzs, Decimal('200000'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('0'))

        self.assertEqual(Chiqim.objects.count(), 1)
        chiqim = Chiqim.objects.first()
        self.assertEqual(chiqim.price, Decimal('200000'))

        self.assertEqual(ChiqimItem.objects.count(), 1)
        item = ChiqimItem.objects.first()
        self.assertEqual(item.price_uzs, Decimal('200000'))
        self.assertEqual(item.xomashyo_harakat, harakat)

        self.assertEqual(Tranzaksiya.objects.count(), 1)
        tr = Tranzaksiya.objects.first()
        self.assertEqual(tr.summa_uzs, Decimal('200000'))
        self.assertEqual(tr.chiqim, chiqim)

    def test_qisman_tolov_va_keyin_tolov_tabi_orqali_yakunlash(self):
        """Qisman to'lov (256000 dan 100000), keyin eski to'lov tabi orqali qolgan 156000 to'langanda 'toliq' bo'ladi."""
        # 1 dona 256,000 so'm
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 1,
            'birlik_narx_uzs': 256000,
            'tolangan_uzs': 100000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'tolov_rejim': 'qisman',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1).first()
        self.assertEqual(harakat.tolov_holati, 'qisman')
        self.assertEqual(harakat.tolangan_uzs, Decimal('100000'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('156000'))

        self.assertEqual(Chiqim.objects.count(), 1)
        self.assertEqual(Tranzaksiya.objects.count(), 1)
        self.assertEqual(Tranzaksiya.objects.first().summa_uzs, Decimal('100000'))

        # Endi eski to'lov tabi orqali (chiqim_qoshish) qolgan 156,000 so'm to'lanadi
        tolov_payload = [{
            'harakat_id': harakat.id,
            'miqdor_uzs': 156000,
        }]
        res_tolov = self.client.post(reverse('xomashyo:chiqim_qoshish'), {
            'chiqim_turi': 'xomashyo_tolov',
            'sana': '2026-09-19',
            'items': json.dumps(tolov_payload),
        })
        self.assertEqual(res_tolov.status_code, 302)

        harakat.refresh_from_db()
        self.assertEqual(harakat.tolov_holati, 'toliq')
        self.assertEqual(harakat.tolangan_uzs, Decimal('256000'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('0'))

        self.assertEqual(Chiqim.objects.count(), 2)
        self.assertEqual(ChiqimItem.objects.count(), 2)
        self.assertEqual(Tranzaksiya.objects.count(), 2)

    def test_kop_qatorli_kirim_har_xil_summalar(self):
        """Ko'p qatorli kirim: turli summalar to'lanadi."""
        items = [
            {
                'xomashyo_id': self.xomashyo1.id,
                'miqdor': 2,
                'birlik_narx_uzs': 50000,  # jami 100000
                'tolangan_uzs': 40000,
            },
            {
                'xomashyo_id': self.xomashyo2.id,
                'miqdor': 50,
                'birlik_narx_uzs': 1000,   # jami 50000
                'tolangan_uzs': 50000,     # to'liq
            }
        ]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'tolov_rejim': 'qisman',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        h1 = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1).first()
        h2 = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo2).first()

        self.assertEqual(h1.tolov_holati, 'qisman')
        self.assertEqual(h1.tolangan_uzs, Decimal('40000'))
        self.assertEqual(h1.qoldiq_uzs, Decimal('60000'))

        self.assertEqual(h2.tolov_holati, 'toliq')
        self.assertEqual(h2.tolangan_uzs, Decimal('50000'))
        self.assertEqual(h2.qoldiq_uzs, Decimal('0'))

        self.assertEqual(Chiqim.objects.count(), 1)
        chiqim = Chiqim.objects.first()
        self.assertEqual(chiqim.price, Decimal('90000'))  # 40000 + 50000
        self.assertEqual(ChiqimItem.objects.count(), 2)

        self.assertEqual(Tranzaksiya.objects.count(), 1)
        self.assertEqual(Tranzaksiya.objects.first().summa_uzs, Decimal('90000'))

    def test_xato_tolov_oshganda_rollback(self):
        """To'lov > jami narx bo'lsa hech narsa saqlanmasligi (rollback) kerak."""
        initial_stock = self.xomashyo1.miqdori
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 1,
            'birlik_narx_uzs': 50000,
            'tolangan_uzs': 60000,  # 50000 dan katta!
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'tolov_rejim': 'qisman',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        self.xomashyo1.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, initial_stock)
        self.assertEqual(XomashyoHarakat.objects.count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)
        self.assertEqual(Tranzaksiya.objects.count(), 0)

    def test_xato_manfiy_tolov_rollback(self):
        """Manfiy to'lov bo'lsa rollback bo'lishi kerak."""
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 1,
            'birlik_narx_uzs': 50000,
            'tolangan_uzs': -1000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'tolov_rejim': 'qisman',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(XomashyoHarakat.objects.count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)

    def test_usd_kurs_bosh_bolganda_ham_ishlaydi(self):
        """USD kurs bo'sh bo'lganda ham xatosiz ishlashi kerak."""
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 2,
            'birlik_narx_uzs': 50000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': self.yb.id,
            'usd_kurs': '',
            'tolov_rejim': 'toliq',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)

        harakat = XomashyoHarakat.objects.first()
        self.assertEqual(harakat.tolov_holati, 'toliq')
        self.assertEqual(harakat.tolangan_uzs, Decimal('100000'))
        self.assertEqual(Chiqim.objects.count(), 1)
        self.assertEqual(Tranzaksiya.objects.count(), 1)

    def test_tolov_qilinganda_yetkazib_beruvchi_majburiy(self):
        """To'lov rejimida yetkazib beruvchi tanlanmasa xato berishi va rollback bo'lishi kerak."""
        items = [{
            'xomashyo_id': self.xomashyo1.id,
            'miqdor': 1,
            'birlik_narx_uzs': 50000,
        }]

        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-19',
            'yetkazib_beruvchi': '',
            'tolov_rejim': 'toliq',
            'items': json.dumps(items),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(XomashyoHarakat.objects.count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)
