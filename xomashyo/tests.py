from decimal import Decimal
import json
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from xomashyo.models import Xomashyo, XomashyoCategory, XomashyoHarakat, YetkazibBeruvchi
from crm.models import Chiqim, ChiqimItem
from budget.models import Tranzaksiya
from xomashyo.services import tolov_yozish

User = get_user_model()


class XomashyoTolovTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="adminuser",
            password="testpassword",
            is_staff=True,
            is_superuser=True
        )
        self.client = Client()
        self.client.login(username="adminuser", password="testpassword")

        self.category = XomashyoCategory.objects.create(
            name="Asosiy",
            turi="real"
        )
        self.yetkazib_beruvchi = YetkazibBeruvchi.objects.create(
            nomi="MCHJ Ta'minot",
            telefon="+998901234567",
            manzil="Toshkent"
        )
        self.xomashyo1 = Xomashyo.objects.create(
            nomi="Yog'och taxta",
            category=self.category,
            miqdori=Decimal('10.00'),
            olchov_birligi='dona',
            minimal_miqdor=Decimal('2.00'),
            narxi=Decimal('10000.00'),
            yetkazib_beruvchi=self.yetkazib_beruvchi
        )
        self.xomashyo2 = Xomashyo.objects.create(
            nomi="Mix 50mm",
            category=self.category,
            miqdori=Decimal('50.00'),
            olchov_birligi='kg',
            minimal_miqdor=Decimal('5.00'),
            narxi=Decimal('20000.00'),
            yetkazib_beruvchi=self.yetkazib_beruvchi
        )

    def test_tolovsiz_qator(self):
        """To'lovsiz qator: harakat tolanmagan bo'ladi, ombor yangilanadi, Chiqim yaratilmaydi."""
        items = [{
            "xomashyo_id": self.xomashyo1.id,
            "miqdor": 5,
            "birlik_narx_uzs": 10000,
            "tolov_holati": "tolanmagan"
        }]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        self.xomashyo1.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, Decimal('15.00'))

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1, harakat_turi='kirim').latest('id')
        self.assertEqual(harakat.tolov_holati, 'tolanmagan')
        self.assertEqual(harakat.jami_narx_uzs, Decimal('50000.00'))
        self.assertEqual(harakat.tolangan_uzs, Decimal('0.00'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('50000.00'))

        self.assertEqual(Chiqim.objects.count(), 0)
        self.assertEqual(ChiqimItem.objects.count(), 0)

    def test_toliq_tolangan_qator(self):
        """To'liq to'langan qator: tolov_holati 'toliq', qoldiq 0, Chiqim va ChiqimItem yaratiladi."""
        items = [{
            "xomashyo_id": self.xomashyo1.id,
            "miqdor": 5,
            "birlik_narx_uzs": 10000,
            "tolov_holati": "toliq"
        }]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        self.xomashyo1.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, Decimal('15.00'))

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1, harakat_turi='kirim').latest('id')
        self.assertEqual(harakat.tolov_holati, 'toliq')
        self.assertEqual(harakat.tolangan_uzs, Decimal('50000.00'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('0.00'))

        self.assertEqual(Chiqim.objects.count(), 1)
        self.assertEqual(ChiqimItem.objects.count(), 1)
        chiqim = Chiqim.objects.first()
        item = ChiqimItem.objects.first()
        self.assertEqual(chiqim.price, Decimal('50000.00'))
        self.assertEqual(item.price_uzs, Decimal('50000.00'))
        self.assertEqual(item.xomashyo_harakat, harakat)

        # Signal orqali Tranzaksiya ham yaratilganini tekshirish
        self.assertTrue(Tranzaksiya.objects.filter(chiqim=chiqim).exists())

    def test_qisman_tolangan_qator(self):
        """Qisman to'langan qator: tolov_holati 'qisman', qoldiq to'g'ri hisoblanadi."""
        items = [{
            "xomashyo_id": self.xomashyo1.id,
            "miqdor": 5,
            "birlik_narx_uzs": 10000,
            "tolov_holati": "qisman",
            "tolangan_uzs": 20000
        }]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        harakat = XomashyoHarakat.objects.filter(xomashyo=self.xomashyo1, harakat_turi='kirim').latest('id')
        self.assertEqual(harakat.tolov_holati, 'qisman')
        self.assertEqual(harakat.tolangan_uzs, Decimal('20000.00'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('30000.00'))

        self.assertEqual(Chiqim.objects.count(), 1)
        self.assertEqual(Chiqim.objects.first().price, Decimal('20000.00'))

    def test_aralash_qatorlar(self):
        """Bir nechta qator, har xil holatlarda: toliq, qisman va tolanmagan."""
        items = [
            {
                "xomashyo_id": self.xomashyo1.id,
                "miqdor": 3,
                "birlik_narx_uzs": 10000,  # Jami 30,000
                "tolov_holati": "toliq"
            },
            {
                "xomashyo_id": self.xomashyo2.id,
                "miqdor": 2,
                "birlik_narx_uzs": 20000,  # Jami 40,000
                "tolov_holati": "qisman",
                "tolangan_uzs": 15000
            },
            {
                "xomashyo_id": self.xomashyo1.id,
                "miqdor": 2,
                "birlik_narx_uzs": 10000,  # Jami 20,000
                "tolov_holati": "tolanmagan"
            }
        ]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        harakatlar = list(XomashyoHarakat.objects.filter(harakat_turi='kirim').order_by('id'))
        self.assertEqual(len(harakatlar), 3)

        # 1: toliq
        self.assertEqual(harakatlar[0].tolov_holati, 'toliq')
        self.assertEqual(harakatlar[0].tolangan_uzs, Decimal('30000.00'))
        self.assertEqual(harakatlar[0].qoldiq_uzs, Decimal('0.00'))

        # 2: qisman
        self.assertEqual(harakatlar[1].tolov_holati, 'qisman')
        self.assertEqual(harakatlar[1].tolangan_uzs, Decimal('15000.00'))
        self.assertEqual(harakatlar[1].qoldiq_uzs, Decimal('25000.00'))

        # 3: tolanmagan
        self.assertEqual(harakatlar[2].tolov_holati, 'tolanmagan')
        self.assertEqual(harakatlar[2].tolangan_uzs, Decimal('0.00'))
        self.assertEqual(harakatlar[2].qoldiq_uzs, Decimal('20000.00'))

        # Chiqimlar: 2 ta yaratilishi kerak (toliq va qisman uchun)
        self.assertEqual(Chiqim.objects.count(), 2)

    def test_xato_tolangan_katta_jami_uzs_rollback(self):
        """tolangan_uzs > jami_uzs bo'lsa xato beradi va HECH NARSA saqlanmaydi (ombor ham o'zgarmaydi)."""
        boshlangich_miqdor1 = self.xomashyo1.miqdori
        boshlangich_miqdor2 = self.xomashyo2.miqdori

        items = [
            {
                "xomashyo_id": self.xomashyo1.id,
                "miqdor": 5,
                "birlik_narx_uzs": 10000,  # Jami 50,000
                "tolov_holati": "toliq"
            },
            {
                "xomashyo_id": self.xomashyo2.id,
                "miqdor": 2,
                "birlik_narx_uzs": 20000,  # Jami 40,000
                "tolov_holati": "qisman",
                "tolangan_uzs": 50000  # XATO: 50,000 > 40,000
            }
        ]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        # Rollback tekshiruvi:
        self.assertEqual(XomashyoHarakat.objects.filter(harakat_turi='kirim').count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)
        self.assertEqual(ChiqimItem.objects.count(), 0)

        self.xomashyo1.refresh_from_db()
        self.xomashyo2.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, boshlangich_miqdor1)
        self.assertEqual(self.xomashyo2.miqdori, boshlangich_miqdor2)

    def test_chiqim_qoshish_xomashyo_tolov_tabi_orqaga_moslik(self):
        """chiqim_qoshish view orqali 'Xomashyo to'lov' tabi refaktordan keyin ham to'g'ri ishlashi."""
        harakat = XomashyoHarakat.objects.create(
            xomashyo=self.xomashyo1,
            harakat_turi='kirim',
            miqdori=Decimal('5'),
            birlik_narx_uzs=Decimal('10000'),
            jami_narx_uzs=Decimal('50000'),
            yetkazib_beruvchi=self.yetkazib_beruvchi,
            foydalanuvchi=self.user
        )
        self.assertEqual(harakat.tolov_holati, 'tolanmagan')
        self.assertEqual(harakat.qoldiq_uzs, Decimal('50000'))

        tolov_items = [{
            "harakat_id": harakat.id,
            "miqdor_uzs": 20000
        }]
        response = self.client.post(reverse('xomashyo:chiqim_qoshish'), {
            'chiqim_turi': 'xomashyo_tolov',
            'sana': '2026-09-23',
            'items': json.dumps(tolov_items)
        })
        self.assertEqual(response.status_code, 302)

        harakat.refresh_from_db()
        self.assertEqual(harakat.tolov_holati, 'qisman')
        self.assertEqual(harakat.tolangan_uzs, Decimal('20000'))
        self.assertEqual(harakat.qoldiq_uzs, Decimal('30000'))

        self.assertEqual(Chiqim.objects.count(), 1)
        self.assertEqual(ChiqimItem.objects.count(), 1)

    def test_waterfall_tortta_qator(self):
        """
        4 ta qatorli kirim, umumiy summa:
        1-2 qator to'liq, 3-qator qisman, 4-qator to'lanmagan.
        Natija: 1 ta Chiqim, 1 ta Tranzaksiya, 3 ta ChiqimItem.
        """
        items = [
            {"xomashyo_id": self.xomashyo1.id, "miqdor": 2, "birlik_narx_uzs": 10000},  # 20,000
            {"xomashyo_id": self.xomashyo2.id, "miqdor": 1, "birlik_narx_uzs": 30000},  # 30,000
            {"xomashyo_id": self.xomashyo1.id, "miqdor": 4, "birlik_narx_uzs": 10000},  # 40,000
            {"xomashyo_id": self.xomashyo2.id, "miqdor": 2, "birlik_narx_uzs": 25000},  # 50,000
        ]
        # Jami qarz = 140,000. To'lov = 70,000.
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'tolov_umumiy_uzs': '70000',
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        harakatlar = list(XomashyoHarakat.objects.filter(harakat_turi='kirim').order_by('id'))
        self.assertEqual(len(harakatlar), 4)

        # 1-chi: 20,000 to'liq yopildi
        self.assertEqual(harakatlar[0].tolov_holati, 'toliq')
        self.assertEqual(harakatlar[0].tolangan_uzs, Decimal('20000.00'))
        self.assertEqual(harakatlar[0].qoldiq_uzs, Decimal('0.00'))

        # 2-chi: 30,000 to'liq yopildi
        self.assertEqual(harakatlar[1].tolov_holati, 'toliq')
        self.assertEqual(harakatlar[1].tolangan_uzs, Decimal('30000.00'))
        self.assertEqual(harakatlar[1].qoldiq_uzs, Decimal('0.00'))

        # 3-chi: 40,000 dan 20,000 qisman yopildi
        self.assertEqual(harakatlar[2].tolov_holati, 'qisman')
        self.assertEqual(harakatlar[2].tolangan_uzs, Decimal('20000.00'))
        self.assertEqual(harakatlar[2].qoldiq_uzs, Decimal('20000.00'))

        # 4-chi: tegilmadi
        self.assertEqual(harakatlar[3].tolov_holati, 'tolanmagan')
        self.assertEqual(harakatlar[3].tolangan_uzs, Decimal('0.00'))
        self.assertEqual(harakatlar[3].qoldiq_uzs, Decimal('50000.00'))

        # 1 ta Chiqim, 3 ta ChiqimItem (chunki 4-qatorga to'lov tegmagan)
        self.assertEqual(Chiqim.objects.count(), 1)
        chiqim = Chiqim.objects.first()
        self.assertEqual(chiqim.price, Decimal('70000.00'))
        self.assertEqual(ChiqimItem.objects.count(), 3)

        # 1 ta Tranzaksiya
        self.assertEqual(Tranzaksiya.objects.filter(chiqim=chiqim).count(), 1)

    def test_waterfall_xato_katta_summa_rollback(self):
        """Umumiy summa > jami qarz bo'lsa xato beradi va HECH NARSA saqlanmaydi (ombor ham o'zgarmaydi)."""
        boshlangich_miqdor1 = self.xomashyo1.miqdori
        boshlangich_miqdor2 = self.xomashyo2.miqdori

        items = [
            {"xomashyo_id": self.xomashyo1.id, "miqdor": 2, "birlik_narx_uzs": 10000},  # 20,000
            {"xomashyo_id": self.xomashyo2.id, "miqdor": 1, "birlik_narx_uzs": 30000},  # 30,000
        ]
        # Jami qarz 50,000. Umumiy summa 80,000 (oshgan).
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'tolov_umumiy_uzs': '80000',
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        # Rollback tekshiruvi:
        self.assertEqual(XomashyoHarakat.objects.filter(harakat_turi='kirim').count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)
        self.assertEqual(ChiqimItem.objects.count(), 0)

        self.xomashyo1.refresh_from_db()
        self.xomashyo2.refresh_from_db()
        self.assertEqual(self.xomashyo1.miqdori, boshlangich_miqdor1)
        self.assertEqual(self.xomashyo2.miqdori, boshlangich_miqdor2)

    def test_ikkala_rejim_bir_vaqtda_xato(self):
        """Ikkala rejim (umumiy summa va qator-bo'yicha to'lov) bir vaqtda to'ldirilsa xato beriladi va hech narsa saqlanmaydi."""
        items = [
            {
                "xomashyo_id": self.xomashyo1.id,
                "miqdor": 2,
                "birlik_narx_uzs": 10000,
                "tolov_holati": "toliq"  # Qator bo'yicha to'lov
            }
        ]
        response = self.client.post(reverse('xomashyo:xomashyo_kirim_qoshish'), {
            'sana': '2026-09-23',
            'yetkazib_beruvchi': self.yetkazib_beruvchi.id,
            'tolov_umumiy_uzs': '20000',  # Bir vaqtda umumiy summa ham yuborildi
            'items': json.dumps(items)
        })
        self.assertEqual(response.status_code, 302)

        # Hech narsa saqlanmasligi kerak:
        self.assertEqual(XomashyoHarakat.objects.filter(harakat_turi='kirim').count(), 0)
        self.assertEqual(Chiqim.objects.count(), 0)

