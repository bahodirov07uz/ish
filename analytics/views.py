from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, Avg, F, Q, Value
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from collections import OrderedDict
import json

import crm.models as crm
import xomashyo.models as xom


def j(val):
    """Decimal / None → float xavfsiz"""
    if val is None:
        return 0
    return float(val)


OY = ['', 'Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn', 'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']


def monthly_map(qs, date_field='oy', val_field='jami'):
    result = OrderedDict()
    for row in qs:
        mo = row[date_field]
        result[f"{mo.year}-{mo.month:02d}"] = j(row[val_field])
    return result


def growth(current, prev):
    if prev and float(prev) > 0:
        return round(((float(current) - float(prev)) / float(prev)) * 100, 1)
    return None


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/analytics.html'
    login_url = 'account_login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today       = timezone.now().date()
        month_start = today.replace(day=1)
        year_start  = today.replace(month=1, day=1)
        last_365    = today - timedelta(days=365)
        last_30     = today - timedelta(days=30)

        prev_month_end   = month_start - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)

        # ── 1. KIRIMLAR ─────────────────────────────────────────────
        kq = crm.Kirim.objects.all()
        D0 = Value(Decimal('0'))

        kirim_bugun  = kq.filter(sana__date=today).aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_oy     = kq.filter(sana__date__gte=month_start).aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_yil    = kq.filter(sana__date__gte=year_start).aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_jami   = kq.aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_usd_oy = kq.filter(sana__date__gte=month_start).aggregate(s=Coalesce(Sum('summa_usd'), D0))['s']
        kirim_prev   = kq.filter(sana__date__gte=prev_month_start, sana__date__lte=prev_month_end).aggregate(s=Coalesce(Sum('summa'), D0))['s']

        # ── 2. SOTUVLAR ─────────────────────────────────────────────
        sq = crm.Sotuv.objects.all()
        sotuv_jami_summa = sq.aggregate(s=Coalesce(Sum('yakuniy_summa'), D0))['s']
        sotuv_tolangan   = sq.aggregate(s=Coalesce(Sum('tolangan_summa'), D0))['s']
        sotuv_qarz       = j(sotuv_jami_summa) - j(sotuv_tolangan)
        sotuv_holat = {
            'tolandi'   : sq.filter(tolov_holati='tolandi').count(),
            'qisman'    : sq.filter(tolov_holati='qisman').count(),
            'tolanmadi' : sq.filter(tolov_holati='tolanmadi').count(),
        }

        # ── 3. CHIQIMLAR ────────────────────────────────────────────
        cq = crm.Chiqim.objects.all()
        chiqim_bugun = cq.filter(created=today).aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_oy    = cq.filter(created__gte=month_start).aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_yil   = cq.filter(created__gte=year_start).aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_jami  = cq.aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_prev  = cq.filter(created__gte=prev_month_start, created__lte=prev_month_end).aggregate(s=Coalesce(Sum('price'), D0))['s']

        # Chiqim kategoriyalar donut
        chiqim_cats = (
            crm.ChiqimItem.objects
            .values('chiqim__category__name')
            .annotate(jami=Sum('price_uzs'))
            .order_by('-jami')[:6]
        )
        chiqim_tur_labels = [x['chiqim__category__name'] or 'Boshqa' for x in chiqim_cats]
        chiqim_tur_vals   = [j(x['jami']) for x in chiqim_cats]

        # ── 4. XOMASHYO KIRIM ───────────────────────────────────────
        hq = xom.XomashyoHarakat.objects.filter(harakat_turi='kirim')
        xom_kirim_uzs  = hq.aggregate(s=Coalesce(Sum('jami_narx_uzs'), D0))['s']
        xom_tolangan   = hq.aggregate(s=Coalesce(Sum('tolangan_uzs'),  D0))['s']
        xom_qarz       = j(xom_kirim_uzs) - j(xom_tolangan)
        xom_kirim_usd  = hq.aggregate(s=Coalesce(Sum('jami_narx_usd'), D0))['s']
        xom_tolov_holat = {
            'tolanmagan' : hq.filter(tolov_holati='tolanmagan').count(),
            'qisman'     : hq.filter(tolov_holati='qisman').count(),
            'toliq'      : hq.filter(tolov_holati='toliq').count(),
        }

        # ── 5. NET FOYDA ────────────────────────────────────────────
        net_foyda_oy  = j(kirim_oy)  - j(chiqim_oy)
        net_foyda_yil = j(kirim_yil) - j(chiqim_yil)

        # ── 6. OYLIK TREND (12 oy) ──────────────────────────────────
        kirim_monthly = monthly_map(
            kq.filter(sana__date__gte=last_365)
              .annotate(oy=TruncMonth('sana'))
              .values('oy').annotate(jami=Sum('summa')).order_by('oy')
        )
        chiqim_monthly = monthly_map(
            cq.filter(created__gte=last_365)
              .annotate(oy=TruncMonth('created'))
              .values('oy').annotate(jami=Sum('price')).order_by('oy')
        )
        all_months = sorted(set(list(kirim_monthly.keys()) + list(chiqim_monthly.keys())))
        trend_labels, trend_kirim, trend_chiqim, trend_foyda = [], [], [], []
        for m in all_months:
            y, mo = int(m[:4]), int(m[5:])
            trend_labels.append(f"{OY[mo]} {str(y)[2:]}")
            k = kirim_monthly.get(m, 0)
            c = chiqim_monthly.get(m, 0)
            trend_kirim.append(k)
            trend_chiqim.append(c)
            trend_foyda.append(round(k - c, 0))

        # ── 7. KUNLIK 30 KUN ────────────────────────────────────────
        daily_qs = (
            kq.filter(sana__date__gte=last_30)
              .annotate(kun=TruncDay('sana'))
              .values('kun').annotate(jami=Sum('summa')).order_by('kun')
        )
        daily_labels = [r['kun'].strftime('%d/%m') for r in daily_qs]
        daily_vals   = [j(r['jami']) for r in daily_qs]

        # ── 8. TOP MAHSULOTLAR ──────────────────────────────────────
        top_mahsulotlar = (
            crm.SotuvItem.objects
            .values('mahsulot__nomi')
            .annotate(jami_miqdor=Sum('miqdor'), jami_summa=Sum('jami'))
            .order_by('-jami_summa')[:8]
        )
        mahsulot_labels = [x['mahsulot__nomi'] for x in top_mahsulotlar]
        mahsulot_vals   = [j(x['jami_summa']) for x in top_mahsulotlar]

        # ── 9. TOP XARIDORLAR ───────────────────────────────────────
        top_xaridorlar = (
            crm.Sotuv.objects
            .values('xaridor__id', 'xaridor__ism', 'xaridor__telefon')
            .annotate(
                jami_xarid=Sum('yakuniy_summa'),
                jami_tolangan=Sum('tolangan_summa'),
                sotuv_soni=Count('id'),
            )
            .order_by('-jami_xarid')[:8]
        )

        # ── 10. QARZLI XARIDORLAR ───────────────────────────────────
        qarzli_xaridorlar = (
            crm.Sotuv.objects
            .exclude(tolov_holati='tolandi')
            .values('xaridor__id', 'xaridor__ism', 'xaridor__telefon')
            .annotate(
                umumiy_qarz=Sum(F('yakuniy_summa') - F('tolangan_summa')),
                qarzli_sotuv_soni=Count('id'),
            )
            .filter(umumiy_qarz__gt=0)
            .order_by('-umumiy_qarz')[:6]
        )

        # ── 11. XOMASHYO TO'LANMAGAN ────────────────────────────────
        xom_qarzlar = (
            xom.XomashyoHarakat.objects
            .filter(harakat_turi='kirim')
            .exclude(tolov_holati__in=['toliq', 'kerak_emas'])
            .select_related('xomashyo', 'yetkazib_beruvchi')
            .order_by('-sana')[:8]
        )

        # ── 12. XOMASHYO KATEGORIYA ─────────────────────────────────
        xom_cat_qs = (
            xom.Xomashyo.objects
            .values('category__name')
            .annotate(jami_miqdor=Sum('miqdori'), dona_soni=Count('id'))
            .order_by('-dona_soni')[:6]
        )
        xom_cat_labels = [x['category__name'] for x in xom_cat_qs]
        xom_cat_vals   = [j(x['jami_miqdor']) for x in xom_cat_qs]

        # ── 13. XARIDOR O'SISH ──────────────────────────────────────
        xaridor_monthly_qs = (
            crm.Xaridor.objects
            .filter(created_at__date__gte=last_365)
            .annotate(oy=TruncMonth('created_at'))
            .values('oy').annotate(soni=Count('id')).order_by('oy')
        )
        xaridor_labels = []
        xaridor_vals   = []
        for r in xaridor_monthly_qs:
            xaridor_labels.append(f"{OY[r['oy'].month]} {str(r['oy'].year)[2:]}")
            xaridor_vals.append(r['soni'])

        ctx.update({
            # Kartalar — kirim
            'kirim_bugun'  : kirim_bugun,
            'kirim_oy'     : kirim_oy,
            'kirim_yil'    : kirim_yil,
            'kirim_jami'   : kirim_jami,
            'kirim_usd_oy' : kirim_usd_oy,
            'kirim_osish'  : growth(kirim_oy, kirim_prev),

            # Kartalar — chiqim
            'chiqim_bugun' : chiqim_bugun,
            'chiqim_oy'    : chiqim_oy,
            'chiqim_yil'   : chiqim_yil,
            'chiqim_jami'  : chiqim_jami,
            'chiqim_osish' : growth(chiqim_oy, chiqim_prev),

            # Foyda
            'net_foyda_oy'  : net_foyda_oy,
            'net_foyda_yil' : net_foyda_yil,

            # Sotuvlar
            'sotuv_jami_summa' : sotuv_jami_summa,
            'sotuv_tolangan'   : sotuv_tolangan,
            'sotuv_qarz'       : sotuv_qarz,
            'sotuv_holat'      : sotuv_holat,

            # Xomashyo
            'xom_kirim_uzs'  : xom_kirim_uzs,
            'xom_kirim_usd'  : xom_kirim_usd,
            'xom_tolangan'   : xom_tolangan,
            'xom_qarz'       : xom_qarz,
            'xom_tolov_holat': xom_tolov_holat,

            # Jadvallar
            'top_xaridorlar'    : top_xaridorlar,
            'top_mahsulotlar'   : top_mahsulotlar,
            'qarzli_xaridorlar' : qarzli_xaridorlar,
            'xom_qarzlar'       : xom_qarzlar,

            # JSON — chartlar
            'trend_labels'      : json.dumps(trend_labels),
            'trend_kirim'       : json.dumps(trend_kirim),
            'trend_chiqim'      : json.dumps(trend_chiqim),
            'trend_foyda'       : json.dumps(trend_foyda),
            'daily_labels'      : json.dumps(daily_labels),
            'daily_vals'        : json.dumps(daily_vals),
            'mahsulot_labels'   : json.dumps(mahsulot_labels),
            'mahsulot_vals'     : json.dumps(mahsulot_vals),
            'xom_cat_labels'    : json.dumps(xom_cat_labels),
            'xom_cat_vals'      : json.dumps(xom_cat_vals),
            'chiqim_tur_labels' : json.dumps(chiqim_tur_labels),
            'chiqim_tur_vals'   : json.dumps(chiqim_tur_vals),
            'xaridor_labels'    : json.dumps(xaridor_labels),
            'xaridor_vals'      : json.dumps(xaridor_vals),

            'today'       : today,
            'month_start' : month_start,
        })
        return ctx