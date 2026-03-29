# budget/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from django.db.models.functions import TruncDay
from decimal import Decimal
from datetime import timedelta
import json

from .models import Byudjet, ByudjetLimit, Tranzaksiya
import crm.models as crm


def _j(v):
    """Decimal yoki None → float (JSON uchun)."""
    return float(v) if v else 0.0


# ── Ro'yxat ──────────────────────────────────────────────────────
class ByudjetListView(LoginRequiredMixin, ListView):
    model = Byudjet
    template_name = 'budget/list.html'
    context_object_name = 'byudjetlar'
    login_url = 'account_login'

    def get_queryset(self):
        return Byudjet.objects.order_by('-davr_boshi')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        ctx['faol'] = Byudjet.objects.filter(
            davr_boshi__lte=today,
            davr_oxiri__gte=today,
        ).first()
        return ctx


# ── Detail ────────────────────────────────────────────────────────
class ByudjetDetailView(LoginRequiredMixin, DetailView):
    model = Byudjet
    template_name = 'budget/detail.html'
    context_object_name = 'b'
    login_url = 'account_login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        b = self.object
        today = timezone.now().date()

        # ── Barcha tranzaksiyalar (davr ichida) ──────────────────
        tranz_qs = Tranzaksiya.objects.filter(
            sana__gte=b.davr_boshi,
            sana__lte=b.davr_oxiri,
        )

        # ── Byudjet sarflari — BITTA query ───────────────────────
        sarflar = tranz_qs.aggregate(
            jami=Sum('summa_uzs', default=Decimal('0')),
            chiqim=Sum('summa_uzs', filter=Q(manba='chiqim'), default=Decimal('0')),
            xomashyo=Sum('summa_uzs', filter=Q(manba='xomashyo'), default=Decimal('0')),
        )
        jami_sarfi   = sarflar['jami']   or Decimal('0')
        chiqim_sarfi = sarflar['chiqim'] or Decimal('0')
        xomashyo_sarfi = sarflar['xomashyo'] or Decimal('0')
        qoldiq = max(b.umumiy_summa - jami_sarfi, Decimal('0'))
        sarfi_foiz = (
            min(round(float(jami_sarfi / b.umumiy_summa * 100), 1), 100)
            if b.umumiy_summa > 0 else 0.0
        )

        # ── Kunlik trend ─────────────────────────────────────────
        daily_qs = (
            tranz_qs
            .annotate(kun=TruncDay('sana'))
            .values('kun', 'manba')
            .annotate(s=Sum('summa_uzs'))
            .order_by('kun', 'manba')
        )

        ck, xk = {}, {}
        for r in daily_qs:
            d = r['kun'].date() if hasattr(r['kun'], 'date') else r['kun']
            if r['manba'] == 'chiqim':
                ck[d] = _j(r['s'])
            else:
                xk[d] = _j(r['s'])

        labels, c_vals, x_vals, cum_vals = [], [], [], []
        cum = 0.0
        cur = b.davr_boshi
        end = min(b.davr_oxiri, today)
        while cur <= end:
            c = ck.get(cur, 0.0)
            x = xk.get(cur, 0.0)
            cum += c + x
            labels.append(cur.strftime('%d/%m'))
            c_vals.append(c)
            x_vals.append(x)
            cum_vals.append(round(cum, 0))
            cur += timedelta(days=1)

        # ── Kategoriya breakdown ──────────────────────────────────
        cats = list(b.sarflar_by_kategoriya())
        cat_labels = [
            f"{r['kategoriya'] or 'Noaniq'} ({r['manba']})" for r in cats
        ]
        cat_vals = [_j(r['jami']) for r in cats]

        # ── Ishchi breakdown ──────────────────────────────────────
        ishchi_sarflar = list(b.sarflar_by_ishchi())

        # ── Limitlar — N+1 muammosiz ─────────────────────────────
        # Limit uchun barcha tranzaksiyalarni bitta query bilan olamiz,
        # keyin Python'da filter qilamiz (limit soni ko'p bo'lmaydi)
        limitlar_raw = list(b.limitlar.all())
        limitlar_data = []
        for lim in limitlar_raw:
            sarfi  = lim.haqiqiy_sarfi   # har biri bitta query — limit soni ko'p bo'lmaydi
            foiz   = lim.foiz
            limitlar_data.append({
                'obj'   : lim,
                'sarfi' : sarfi,
                'foiz'  : foiz,
                'holat' : lim.holat,
                'qoldiq': max(lim.limit_summa - sarfi, Decimal('0')),
            })

        # ── So'nggi 30 tranzaksiya ────────────────────────────────
        so_tranz = tranz_qs.select_related(
            'ishchi',
            'foydalanuvchi',
            'chiqim__category',
            'xomashyo_harakat__xomashyo',
        ).order_by('-sana', '-created_at')[:30]

        # ── Limit qo'shish formi uchun ────────────────────────────
        chiqim_turlar = crm.ChiqimTuri.objects.all()

        ctx.update({
            # Hisoblangan summalar (template'ga tayyor)
            'jami_sarfi'      : jami_sarfi,
            'chiqim_sarfi'    : chiqim_sarfi,
            'xomashyo_sarfi'  : xomashyo_sarfi,
            'qoldiq'          : qoldiq,
            'sarfi_foiz'      : sarfi_foiz,
            'holat'           : _holat(sarfi_foiz),

            # Jadvallar
            'limitlar_data'   : limitlar_data,
            'so_tranz'        : so_tranz,
            'ishchi_sarflar'  : ishchi_sarflar,
            'cats'            : cats,
            'chiqim_turlar'   : chiqim_turlar,

            # Chart.js uchun JSON
            'chart_labels'    : json.dumps(labels),
            'chart_chiqim'    : json.dumps(c_vals),
            'chart_xomashyo'  : json.dumps(x_vals),
            'chart_cum'       : json.dumps(cum_vals),
            'cat_labels'      : json.dumps(cat_labels),
            'cat_vals'        : json.dumps(cat_vals),
            'byudjet_limit_j' : json.dumps(_j(b.umumiy_summa)),
        })
        return ctx


def _holat(foiz: float) -> str:
    if foiz >= 100: return 'oshib_ketdi'
    if foiz >= 90:  return 'xavfli'
    if foiz >= 75:  return 'ogoh'
    return 'xavfsiz'


# ── Yaratish ─────────────────────────────────────────────────────
class ByudjetCreateView(LoginRequiredMixin, CreateView):
    model = Byudjet
    template_name = 'budget/form.html'
    fields = ['nomi', 'davr_boshi', 'davr_oxiri', 'umumiy_summa', 'izoh']
    login_url = 'account_login'

    def form_valid(self, form):
        form.instance.yaratgan = self.request.user
        messages.success(self.request, "✅ Byudjet yaratildi!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('budget:detail', kwargs={'pk': self.object.pk})


# ── Tahrirlash ───────────────────────────────────────────────────
class ByudjetUpdateView(LoginRequiredMixin, UpdateView):
    model = Byudjet
    template_name = 'budget/form.html'
    fields = ['nomi', 'davr_boshi', 'davr_oxiri', 'umumiy_summa', 'izoh']
    login_url = 'account_login'

    def form_valid(self, form):
        messages.success(self.request, "✅ Yangilandi!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('budget:detail', kwargs={'pk': self.object.pk})


# ── Limit CRUD ───────────────────────────────────────────────────
def limit_qoshish(request, pk):
    b = get_object_or_404(Byudjet, pk=pk)
    if request.method == 'POST':
        try:
            summa_str = request.POST.get('limit_summa', '0').replace(' ', '').replace(',', '')
            ByudjetLimit.objects.create(
                byudjet     = b,
                nomi        = request.POST.get('nomi', '').strip(),
                manba       = request.POST.get('manba', ''),
                kategoriya  = request.POST.get('kategoriya', '').strip(),
                limit_summa = Decimal(summa_str or '0'),
            )
            messages.success(request, "✅ Limit qo'shildi!")
        except Exception as e:
            messages.error(request, f"Xatolik: {e}")
    return redirect('budget:detail', pk=pk)


def limit_ochirish(request, pk):
    lim = get_object_or_404(ByudjetLimit, pk=pk)
    byudjet_pk = lim.byudjet_id
    lim.delete()
    messages.success(request, "Limit o'chirildi.")
    return redirect('budget:detail', pk=byudjet_pk)


# ── Tranzaksiya ro'yxati (filter bilan) ──────────────────────────
class TranzaksiyaListView(LoginRequiredMixin, ListView):
    model = Tranzaksiya
    template_name = 'budget/tranzaksiyalar.html'
    context_object_name = 'tranzaksiyalar'
    paginate_by = 50
    login_url = 'account_login'

    def get_queryset(self):
        qs = Tranzaksiya.objects.select_related(
            'ishchi',
            'chiqim__category',
            'xomashyo_harakat__xomashyo',
            'foydalanuvchi',
        ).order_by('-sana', '-created_at')

        manba = self.request.GET.get('manba', '')
        if manba:
            qs = qs.filter(manba=manba)

        date_from = self.request.GET.get('date_from', '')
        date_to   = self.request.GET.get('date_to', '')
        if date_from:
            qs = qs.filter(sana__gte=date_from)
        if date_to:
            qs = qs.filter(sana__lte=date_to)

        ishchi_id = self.request.GET.get('ishchi', '')
        if ishchi_id and ishchi_id.isdigit():
            qs = qs.filter(ishchi_id=int(ishchi_id))

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # get_queryset() qayta chaqirilmaydi — paginator filtrlangan QS ishlatadi
        filtered_qs = self.get_queryset()

        agg = filtered_qs.aggregate(
            jami_uzs=Sum('summa_uzs', default=Decimal('0')),
            jami_usd=Sum('summa_usd', default=Decimal('0')),
        )
        ctx['jami_uzs']     = agg['jami_uzs'] or 0
        ctx['jami_usd']     = agg['jami_usd'] or 0
        ctx['manba_filter'] = self.request.GET.get('manba', '')
        ctx['date_from']    = self.request.GET.get('date_from', '')
        ctx['date_to']      = self.request.GET.get('date_to', '')
        ctx['ishchi_filter']= self.request.GET.get('ishchi', '')
        ctx['ishchilar']    = crm.Ishchi.objects.filter(is_active=True).order_by('ism')
        return ctx