# budget/views.py
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count
from django.db.models.functions import TruncDay, TruncMonth
from decimal import Decimal
from collections import OrderedDict
from datetime import timedelta
import json

from .models import Byudjet, ByudjetLimit, Tranzaksiya
import crm.models as crm


def j(v):
    return float(v) if v else 0


# ── Ro'yxat ──────────────────────────────────────────────────────
class ByudjetListView(LoginRequiredMixin, ListView):
    model = Byudjet
    template_name = 'budget/list.html'
    context_object_name = 'byudjetlar'
    login_url = 'account_login'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        ctx['faol'] = Byudjet.objects.filter(
            davr_boshi__lte=today, davr_oxiri__gte=today
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

        tranz = Tranzaksiya.objects.filter(
            sana__gte=b.davr_boshi,
            sana__lte=b.davr_oxiri,
        )

        # ── Kunlik trend ─────────────────────────────────────────
        daily_qs = (
            tranz
            .annotate(kun=TruncDay('sana'))
            .values('kun', 'manba')
            .annotate(s=Sum('summa_uzs'))
            .order_by('kun', 'manba')
        )

        ck, xk = {}, {}
        for r in daily_qs:
            d = r['kun'].date()
            if r['manba'] == 'chiqim':
                ck[d] = j(r['s'])
            else:
                xk[d] = j(r['s'])

        labels, c_vals, x_vals, cum_vals = [], [], [], []
        cum = 0.0
        cur = b.davr_boshi
        today = timezone.now().date()
        while cur <= min(b.davr_oxiri, today):
            c = ck.get(cur, 0)
            x = xk.get(cur, 0)
            cum += c + x
            labels.append(cur.strftime('%d/%m'))
            c_vals.append(c)
            x_vals.append(x)
            cum_vals.append(round(cum, 0))
            cur += timedelta(days=1)

        # ── Kategoriya breakdown ──────────────────────────────────
        cats = list(b.sarflar_by_kategoriya())
        cat_labels = [f"{r['kategoriya'] or 'Noaniq'} ({r['manba']})" for r in cats]
        cat_vals   = [j(r['jami']) for r in cats]

        # ── Ishchi breakdown ──────────────────────────────────────
        ishchi_sarflar = list(b.sarflar_by_ishchi())

        # ── Limitlar ─────────────────────────────────────────────
        limitlar_data = []
        for lim in b.limitlar.all():
            limitlar_data.append({
                'obj'   : lim,
                'sarfi' : lim.haqiqiy_sarfi,
                'foiz'  : lim.foiz,
                'holat' : lim.holat,
                'qoldiq': lim.limit_summa - lim.haqiqiy_sarfi,
            })

        # ── So'nggi tranzaksiyalar ────────────────────────────────
        so_tranz = tranz.select_related(
            'ishchi', 'foydalanuvchi',
            'chiqim__category',
            'xomashyo_harakat__xomashyo',
        ).order_by('-sana', '-created_at')[:30]

        # ── Limit form uchun ──────────────────────────────────────
        chiqim_turlar = crm.ChiqimTuri.objects.all()

        ctx.update({
            'limitlar_data'   : limitlar_data,
            'so_tranz'        : so_tranz,
            'ishchi_sarflar'  : ishchi_sarflar,
            'cats'            : cats,
            'chiqim_turlar'   : chiqim_turlar,

            'chart_labels'    : json.dumps(labels),
            'chart_chiqim'    : json.dumps(c_vals),
            'chart_xomashyo'  : json.dumps(x_vals),
            'chart_cum'       : json.dumps(cum_vals),
            'cat_labels'      : json.dumps(cat_labels),
            'cat_vals'        : json.dumps(cat_vals),
            'byudjet_limit_j' : json.dumps(j(b.umumiy_summa)),
        })
        return ctx


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
            ByudjetLimit.objects.create(
                byudjet     = b,
                nomi        = request.POST.get('nomi', ''),
                manba       = request.POST.get('manba', ''),
                kategoriya  = request.POST.get('kategoriya', ''),
                limit_summa = Decimal(request.POST.get('limit_summa', '0')),
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
            'ishchi', 'chiqim__category',
            'xomashyo_harakat__xomashyo',
            'foydalanuvchi',
        ).order_by('-sana', '-created_at')

        # Filterlar
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
        if ishchi_id:
            qs = qs.filter(ishchi_id=ishchi_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        ctx['jami_uzs']    = qs.aggregate(s=Sum('summa_uzs'))['s'] or 0
        ctx['jami_usd']    = qs.aggregate(s=Sum('summa_usd'))['s'] or 0
        ctx['manba_filter']= self.request.GET.get('manba', '')
        ctx['date_from']   = self.request.GET.get('date_from', '')
        ctx['date_to']     = self.request.GET.get('date_to', '')
        ctx['ishchilar']   = crm.Ishchi.objects.filter(is_active=True).order_by('ism')
        return ctx