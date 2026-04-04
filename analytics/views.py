from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, F, Value
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from collections import OrderedDict
import json

import crm.models as crm
import xomashyo.models as xom


# ── Helpers ────────────────────────────────────────────────────────────────

def j(val):
    """Decimal / None → float xavfsiz"""
    if val is None:
        return 0
    return float(val)


OY = ['', 'Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn', 'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']

PRESET_CHOICES = [
    ('today',        'Bugun'),
    ('yesterday',    'Kecha'),
    ('this_week',    'Bu hafta'),
    ('last_week',    'Otgan hafta'),
    ('this_month',   'Bu oy'),
    ('last_month',   'Otgan oy'),
    ('last_30',      'Songgi 30 kun'),
    ('last_90',      'Songgi 90 kun'),
    ('this_year',    'Bu yil'),
    ('last_365',     'Songgi 365 kun'),
    ('all_time',     'Barcha vaqt'),
    ('custom',       'Maxsus'),
]


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


def parse_date(val):
    """String → date yoki None"""
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def resolve_dates(preset, date_from_str, date_to_str, today):
    """
    Preset yoki custom range → (date_from, date_to, label)
    Har doim date_from <= date_to bo'ladi.
    """
    def week_start(d):
        return d - timedelta(days=d.weekday())

    month_start = today.replace(day=1)

    if preset == 'today':
        return today, today, 'Bugun'

    if preset == 'yesterday':
        y = today - timedelta(days=1)
        return y, y, 'Kecha'

    if preset == 'this_week':
        ws = week_start(today)
        return ws, today, 'Bu hafta'

    if preset == 'last_week':
        ws = week_start(today) - timedelta(days=7)
        return ws, ws + timedelta(days=6), 'Otgan hafta'

    if preset == 'this_month':
        return month_start, today, 'Bu oy'

    if preset == 'last_month':
        end = month_start - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, 'Otgan oy'

    if preset == 'last_30':
        return today - timedelta(days=29), today, 'Songgi 30 kun'

    if preset == 'last_90':
        return today - timedelta(days=89), today, 'Songgi 90 kun'

    if preset == 'this_year':
        return today.replace(month=1, day=1), today, f'{today.year}-yil'

    if preset == 'last_365':
        return today - timedelta(days=364), today, 'Songgi 365 kun'

    if preset == 'all_time':
        return date(2000, 1, 1), today, 'Barcha vaqt'

    # custom
    df = parse_date(date_from_str)
    dt = parse_date(date_to_str)
    if not df and not dt:
        return month_start, today, 'Bu oy'
    if not df:
        df = dt
    if not dt:
        dt = df
    if df > dt:
        df, dt = dt, df
    label = f"{df.strftime('%d.%m.%Y')} – {dt.strftime('%d.%m.%Y')}"
    return df, dt, label


class AnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/analytics.html'
    login_url = 'account_login'

    # ── request parsing ────────────────────────────────────────
    def _get_range(self):
        today = timezone.now().date()
        preset = self.request.GET.get('preset', 'this_month')
        date_from_str = self.request.GET.get('date_from', '')
        date_to_str   = self.request.GET.get('date_to', '')

        valid_presets = {k for k, _ in PRESET_CHOICES}
        if preset not in valid_presets:
            preset = 'this_month'

        date_from, date_to, range_label = resolve_dates(
            preset, date_from_str, date_to_str, today
        )
        return today, date_from, date_to, range_label, preset

    # ── main context ───────────────────────────────────────────
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today, date_from, date_to, range_label, preset = self._get_range()

        D0 = Value(Decimal('0'))

        # Period length — taqqoslash uchun
        delta_days  = (date_to - date_from).days + 1
        prev_to     = date_from - timedelta(days=1)
        prev_from   = prev_to - timedelta(days=delta_days - 1)

        # ── field type detection ─────────────────────────────────────
        # DateTimeField → __date__ lookup kerak
        # DateField     → to'g'ridan-to'g'ri __gte / __lte
        from django.db.models import DateTimeField as DTF

        def _is_datetime(model, field_name):
            try:
                return isinstance(model._meta.get_field(field_name), DTF)
            except Exception:
                return False

        # ── 1. KIRIMLAR ─────────────────────────────────────────────
        kq = crm.Kirim.objects.all()

        # Kirim.sana — DateTimeField yoki DateField?
        if _is_datetime(crm.Kirim, 'sana'):
            kirim_period  = kq.filter(sana__date__gte=date_from, sana__date__lte=date_to)
            kirim_prev_qs = kq.filter(sana__date__gte=prev_from, sana__date__lte=prev_to)
            kirim_bugun   = kq.filter(sana__date=today).aggregate(s=Coalesce(Sum('summa'), D0))['s']
        else:
            kirim_period  = kq.filter(sana__gte=date_from, sana__lte=date_to)
            kirim_prev_qs = kq.filter(sana__gte=prev_from, sana__lte=prev_to)
            kirim_bugun   = kq.filter(sana=today).aggregate(s=Coalesce(Sum('summa'), D0))['s']

        kirim_summa   = kirim_period.aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_usd     = kirim_period.aggregate(s=Coalesce(Sum('summa_usd'), D0))['s']
        kirim_prev    = kirim_prev_qs.aggregate(s=Coalesce(Sum('summa'), D0))['s']
        kirim_jami    = kq.aggregate(s=Coalesce(Sum('summa'), D0))['s']

        # ── 2. SOTUVLAR ─────────────────────────────────────────────
        sq = crm.Sotuv.objects.all()

        # Sotuv date field nomini aniqlash
        _sotuv_date_field = None
        for _fn in ('sana', 'created_at', 'created', 'date'):
            try:
                crm.Sotuv._meta.get_field(_fn)
                _sotuv_date_field = _fn
                break
            except Exception:
                pass

        if _sotuv_date_field and _is_datetime(crm.Sotuv, _sotuv_date_field):
            sq_period = sq.filter(**{
                f'{_sotuv_date_field}__date__gte': date_from,
                f'{_sotuv_date_field}__date__lte': date_to,
            })
        elif _sotuv_date_field:
            sq_period = sq.filter(**{
                f'{_sotuv_date_field}__gte': date_from,
                f'{_sotuv_date_field}__lte': date_to,
            })
        else:
            sq_period = sq

        sotuv_jami_summa = sq_period.aggregate(s=Coalesce(Sum('yakuniy_summa'), D0))['s']
        sotuv_tolangan   = sq_period.aggregate(s=Coalesce(Sum('tolangan_summa'), D0))['s']
        sotuv_qarz       = j(sotuv_jami_summa) - j(sotuv_tolangan)
        sotuv_holat = {
            'tolandi'   : sq_period.filter(tolov_holati='tolandi').count(),
            'qisman'    : sq_period.filter(tolov_holati='qisman').count(),
            'tolanmadi' : sq_period.filter(tolov_holati='tolanmadi').count(),
        }

        # ── 3. CHIQIMLAR ────────────────────────────────────────────
        cq = crm.Chiqim.objects.all()

        # Chiqim date field: 'created' DateField yoki DateTimeField?
        _chiqim_dt = _is_datetime(crm.Chiqim, 'created')
        if _chiqim_dt:
            chiqim_period  = cq.filter(created__date__gte=date_from, created__date__lte=date_to)
            chiqim_prev_qs = cq.filter(created__date__gte=prev_from, created__date__lte=prev_to)
            chiqim_bugun   = cq.filter(created__date=today).aggregate(s=Coalesce(Sum('price'), D0))['s']
            _chiqim_item_filter = {'chiqim__created__date__gte': date_from, 'chiqim__created__date__lte': date_to}
        else:
            chiqim_period  = cq.filter(created__gte=date_from, created__lte=date_to)
            chiqim_prev_qs = cq.filter(created__gte=prev_from, created__lte=prev_to)
            chiqim_bugun   = cq.filter(created=today).aggregate(s=Coalesce(Sum('price'), D0))['s']
            _chiqim_item_filter = {'chiqim__created__gte': date_from, 'chiqim__created__lte': date_to}

        chiqim_summa  = chiqim_period.aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_prev   = chiqim_prev_qs.aggregate(s=Coalesce(Sum('price'), D0))['s']
        chiqim_jami   = cq.aggregate(s=Coalesce(Sum('price'), D0))['s']

        # Chiqim kategoriyalar donut
        chiqim_cats = (
            crm.ChiqimItem.objects
            .filter(**_chiqim_item_filter)
            .values('chiqim__category__name')
            .annotate(jami=Sum('price_uzs'))
            .order_by('-jami')[:6]
        )
        chiqim_tur_labels = [x['chiqim__category__name'] or 'Boshqa' for x in chiqim_cats]
        chiqim_tur_vals   = [j(x['jami']) for x in chiqim_cats]

        # ── 4. XOMASHYO KIRIM ───────────────────────────────────────
        hq = xom.XomashyoHarakat.objects.filter(harakat_turi='kirim')

        _xom_dt = _is_datetime(xom.XomashyoHarakat, 'sana')
        if _xom_dt:
            hq_period  = hq.filter(sana__date__gte=date_from, sana__date__lte=date_to)
            _xom_qarz_filter = {'harakat_turi': 'kirim', 'sana__date__gte': date_from, 'sana__date__lte': date_to}
        else:
            hq_period  = hq.filter(sana__gte=date_from, sana__lte=date_to)
            _xom_qarz_filter = {'harakat_turi': 'kirim', 'sana__gte': date_from, 'sana__lte': date_to}

        xom_kirim_uzs = hq_period.aggregate(s=Coalesce(Sum('jami_narx_uzs'), D0))['s']
        xom_tolangan  = hq_period.aggregate(s=Coalesce(Sum('tolangan_uzs'),  D0))['s']
        xom_qarz      = j(xom_kirim_uzs) - j(xom_tolangan)
        xom_kirim_usd = hq_period.aggregate(s=Coalesce(Sum('jami_narx_usd'), D0))['s']
        xom_tolov_holat = {
            'tolanmagan' : hq_period.filter(tolov_holati='tolanmagan').count(),
            'qisman'     : hq_period.filter(tolov_holati='qisman').count(),
            'toliq'      : hq_period.filter(tolov_holati='toliq').count(),
        }

        # ── 5. NET FOYDA ────────────────────────────────────────────
        net_foyda     = j(kirim_summa) - j(chiqim_summa)
        net_foyda_prev = j(kirim_prev) - j(chiqim_prev)

        # ── 6. TREND CHART (period ichida oylik yoki kunlik) ─────────
        # 90 kundan ko'p bo'lsa → oylik; kamroq bo'lsa → kunlik
        use_monthly_trend = delta_days > 90

        if use_monthly_trend:
            kirim_monthly = monthly_map(
                kirim_period
                  .annotate(oy=TruncMonth('sana'))
                  .values('oy').annotate(jami=Sum('summa')).order_by('oy')
            )
            chiqim_monthly = monthly_map(
                chiqim_period
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
        else:
            # Kunlik
            kirim_daily_qs = (
                kirim_period
                  .annotate(kun=TruncDay('sana'))
                  .values('kun').annotate(jami=Sum('summa')).order_by('kun')
            )
            chiqim_daily_qs = (
                chiqim_period
                  .annotate(kun=TruncDay('created'))
                  .values('kun').annotate(jami=Sum('price')).order_by('kun')
            )
            kirim_d  = {r['kun'].strftime('%Y-%m-%d'): j(r['jami']) for r in kirim_daily_qs}
            chiqim_d = {r['kun'].strftime('%Y-%m-%d'): j(r['jami']) for r in chiqim_daily_qs}
            all_days = sorted(set(list(kirim_d.keys()) + list(chiqim_d.keys())))
            trend_labels, trend_kirim, trend_chiqim, trend_foyda = [], [], [], []
            for d_str in all_days:
                d_obj = date.fromisoformat(d_str)
                trend_labels.append(d_obj.strftime('%d/%m'))
                k = kirim_d.get(d_str, 0)
                c = chiqim_d.get(d_str, 0)
                trend_kirim.append(k)
                trend_chiqim.append(c)
                trend_foyda.append(round(k - c, 0))

        # ── 7. TOP MAHSULOTLAR ──────────────────────────────────────
        top_mahsulotlar = (
            crm.SotuvItem.objects
            .filter(sotuv__in=sq_period)
            .values('mahsulot__nomi')
            .annotate(jami_miqdor=Sum('miqdor'), jami_summa=Sum('jami'))
            .order_by('-jami_summa')[:8]
        )
        mahsulot_labels = [x['mahsulot__nomi'] for x in top_mahsulotlar]
        mahsulot_vals   = [j(x['jami_summa']) for x in top_mahsulotlar]

        # ── 8. TOP XARIDORLAR ───────────────────────────────────────
        top_xaridorlar = (
            sq_period
            .values('xaridor__id', 'xaridor__ism', 'xaridor__telefon')
            .annotate(
                jami_xarid=Sum('yakuniy_summa'),
                jami_tolangan=Sum('tolangan_summa'),
                sotuv_soni=Count('id'),
            )
            .order_by('-jami_xarid')[:8]
        )

        # ── 9. QARZLI XARIDORLAR ────────────────────────────────────
        qarzli_xaridorlar = (
            sq_period
            .exclude(tolov_holati='tolandi')
            .values('xaridor__id', 'xaridor__ism', 'xaridor__telefon')
            .annotate(
                umumiy_qarz=Sum(F('yakuniy_summa') - F('tolangan_summa')),
                qarzli_sotuv_soni=Count('id'),
            )
            .filter(umumiy_qarz__gt=0)
            .order_by('-umumiy_qarz')[:6]
        )

        # ── 10. XOMASHYO TO'LANMAGAN ─────────────────────────────────
        xom_qarzlar = (
            xom.XomashyoHarakat.objects
            .filter(**_xom_qarz_filter)
            .exclude(tolov_holati__in=['toliq', 'kerak_emas'])
            .select_related('xomashyo', 'yetkazib_beruvchi')
            .order_by('-sana')[:8]
        )

        # ── 11. XOMASHYO KATEGORIYA ──────────────────────────────────
        xom_cat_qs = (
            xom.Xomashyo.objects
            .values('category__name')
            .annotate(jami_miqdor=Sum('miqdori'), dona_soni=Count('id'))
            .order_by('-dona_soni')[:6]
        )
        xom_cat_labels = [x['category__name'] for x in xom_cat_qs]
        xom_cat_vals   = [j(x['jami_miqdor']) for x in xom_cat_qs]

        # ── 12. XARIDOR O'SISH ───────────────────────────────────────
        _xaridor_dt = _is_datetime(crm.Xaridor, 'created_at')
        if _xaridor_dt:
            _xaridor_filter = {'created_at__date__gte': date_from, 'created_at__date__lte': date_to}
        else:
            _xaridor_filter = {'created_at__gte': date_from, 'created_at__lte': date_to}

        xaridor_monthly_qs = (
            crm.Xaridor.objects
            .filter(**_xaridor_filter)
            .annotate(oy=TruncMonth('created_at'))
            .values('oy').annotate(soni=Count('id')).order_by('oy')
        )
        xaridor_labels = []
        xaridor_vals   = []
        for r in xaridor_monthly_qs:
            xaridor_labels.append(f"{OY[r['oy'].month]} {str(r['oy'].year)[2:]}")
            xaridor_vals.append(r['soni'])

        # ── Context ─────────────────────────────────────────────────
        ctx.update({
            # Filter state
            'preset'          : preset,
            'preset_choices'  : PRESET_CHOICES,
            'date_from'       : date_from,
            'date_to'         : date_to,
            'date_from_str'   : date_from.isoformat(),
            'date_to_str'     : date_to.isoformat(),
            'range_label'     : range_label,
            'use_monthly_trend': use_monthly_trend,

            # Kartalar — kirim
            'kirim_summa'    : kirim_summa,
            'kirim_bugun'    : kirim_bugun,
            'kirim_jami'     : kirim_jami,
            'kirim_usd'      : kirim_usd,
            'kirim_osish'    : growth(kirim_summa, kirim_prev),

            # Kartalar — chiqim
            'chiqim_summa'   : chiqim_summa,
            'chiqim_bugun'   : chiqim_bugun,
            'chiqim_jami'    : chiqim_jami,
            'chiqim_osish'   : growth(chiqim_summa, chiqim_prev),

            # Foyda
            'net_foyda'      : net_foyda,
            'net_foyda_osish': growth(net_foyda, net_foyda_prev),

            # Sotuvlar
            'sotuv_jami_summa' : sotuv_jami_summa,
            'sotuv_tolangan'   : sotuv_tolangan,
            'sotuv_qarz'       : sotuv_qarz,
            'sotuv_holat'      : sotuv_holat,

            # Xomashyo
            'xom_kirim_uzs'   : xom_kirim_uzs,
            'xom_kirim_usd'   : xom_kirim_usd,
            'xom_tolangan'    : xom_tolangan,
            'xom_qarz'        : xom_qarz,
            'xom_tolov_holat' : xom_tolov_holat,
            'xom_cat_qs'      : xom_cat_qs,

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
            'mahsulot_labels'   : json.dumps(mahsulot_labels),
            'mahsulot_vals'     : json.dumps(mahsulot_vals),
            'xom_cat_labels'    : json.dumps(xom_cat_labels),
            'xom_cat_vals'      : json.dumps(xom_cat_vals),
            'chiqim_tur_labels' : json.dumps(chiqim_tur_labels),
            'chiqim_tur_vals'   : json.dumps(chiqim_tur_vals),
            'xaridor_labels'    : json.dumps(xaridor_labels),
            'xaridor_vals'      : json.dumps(xaridor_vals),
            'sotuv_holat_json'  : json.dumps(sotuv_holat),

            'today'       : today,
        })
        return ctx