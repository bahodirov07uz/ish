#xomashyo app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView,DetailView,View
from django.db.models import Sum,F,DecimalField, Q
from datetime import date,datetime
import decimal
from decimal import Decimal,ROUND_DOWN
from django.db import transaction
from django.contrib.auth.decorators import login_required,user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.decorators import method_decorator

from django.db.models.functions import Coalesce
from crm.models import Chiqim, ChiqimTuri,Ishchi,ChiqimItem
from xomashyo.models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi,XomashyoCategory,XomashyoVariant
from crm.views import AdminRequiredMixin,is_admin
import json

def _parse_sana(sana_str):
    """
    'YYYY-MM-DD' formatidan date obyekti qaytaradi.
    Bo'sh yoki noto'g'ri bo'lsa bugungi sana.
    """
    if sana_str:
        try:
            return datetime.strptime(sana_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    return date.today()


def _xomashyo_to_dict(x):
    """Xomashyo → JSON-safe dict (JS uchun)."""
    narx = float(x.narxi) if x.narxi else 0
    cat  = x.category.name if x.category_id else ''
    label = x.nomi + (f' ({cat})' if cat else '') + f" — {narx:,.0f} so'm/{x.get_olchov_birligi_display()}"
    return {
        'id':     str(x.id),
        'label':  label,
        'search': x.nomi.lower(),
        'narx':   narx,
        'olchov': x.get_olchov_birligi_display(),
    }


# ─────────────────────────────────────────────────────────────────
# LIST VIEW
# ─────────────────────────────────────────────────────────────────

class ChiqimListView(AdminRequiredMixin, ListView):
    model = Chiqim
    template_name = 'chiqim.html'
    context_object_name = 'chiqimlar'
    ordering = ['-created']
    paginate_by = 50

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        context['bugungi_chiqim'] = Chiqim.objects.filter(
            created=today
        ).aggregate(Sum('price'))['price__sum'] or 0

        context['oylik_chiqim'] = Chiqim.objects.filter(
            created__year=today.year,
            created__month=today.month,
        ).aggregate(Sum('price'))['price__sum'] or 0

        context['jami_chiqim'] = Chiqim.objects.aggregate(
            Sum('price')
        )['price__sum'] or 0

        context['today_str'] = today.strftime('%Y-%m-%d')

        # ── Xomashyo (faqat active) ──────────────────────────────
        xomashyolar = Xomashyo.objects.filter(
            holati='active'
        ).select_related('category').order_by('nomi')

        # ── Qarzdor harakatlar (to'lanmagan / qisman) ───────────
        qarzdor_harakatlar = XomashyoHarakat.objects.filter(
            harakat_turi='kirim',
            tolov_holati__in=['tolanmagan', 'qisman']
        ).select_related('xomashyo', 'yetkazib_beruvchi').order_by('-sana')

        context['xomashyolar']          = xomashyolar
        context['chiqim_turlari']       = ChiqimTuri.objects.all()
        context['yetkazib_beruvchilar'] = YetkazibBeruvchi.objects.all()
        context['qarzdor_harakatlar']   = qarzdor_harakatlar

        # Jami qarz
        context['jami_qarz_uzs'] = sum(h.qoldiq_uzs for h in qarzdor_harakatlar)

        # JSON (frontend uchun)
        context['xomashyo_json'] = [_xomashyo_to_dict(x) for x in xomashyolar]
        context['cats_json'] = [
            {'id': str(t.id), 'name': t.name}
            for t in ChiqimTuri.objects.all()
        ]
        context['qarzdor_json'] = [
            {
                'id':           str(h.id),
                'nomi':         h.xomashyo.nomi if h.xomashyo else '—',
                'sana':         h.sana.strftime('%d.%m.%Y') if h.sana else None,
                'jami_uzs':     float(h.jami_narx_uzs),
                'jami_usd':     float(h.jami_narx_usd or 0),
                'tolangan_uzs': float(h.tolangan_uzs),
                'qoldiq_uzs':   float(h.qoldiq_uzs),
                'qoldiq_usd':   float(h.qoldiq_usd or 0),
                'usd_kurs':     float(h.usd_kurs or 0),
                'yetkazib':     h.yetkazib_beruvchi.nomi if h.yetkazib_beruvchi else '—',
                'foiz':         h.tolov_foizi,
            }
            for h in qarzdor_harakatlar
        ]
        return context
    


# ─────────────────────────────────────────────────────────────────
# XOMASHYO KIRIM QO'SHISH
# Ombor yangilanadi. Chiqim YARATILMAYDI (to'lov alohida).
# ─────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def xomashyo_kirim_qoshish(request):
    """
    POST fields:
      sana              = 'YYYY-MM-DD'
      yetkazib_beruvchi = <id>  (ixtiyoriy)
      usd_kurs          = kurs  (ixtiyoriy)
      izoh              = '...' (ixtiyoriy)
      items             = JSON

    items JSON:
      [{
        "xomashyo_id":    1,
        "miqdor":         5,
        "birlik_narx_uzs": 12000,
        "birlik_narx_usd": 1.0,   (ixtiyoriy)
      }, ...]
    """
    if request.method != 'POST':
        return redirect('xomashyo:chiqimlar')

    izoh    = request.POST.get('izoh', '').strip()
    yb_id   = request.POST.get('yetkazib_beruvchi') or None
    sana    = _parse_sana(request.POST.get('sana'))
    usd_kurs_str = request.POST.get('usd_kurs', '').strip()

    try:
        usd_kurs = Decimal(usd_kurs_str) if usd_kurs_str else None
    except decimal.InvalidOperation:
        usd_kurs = None

    try:
        rows = json.loads(request.POST.get('items', '[]'))
        if not rows:
            messages.error(request, "Kamida bitta xomashyo qatori kerak!")
            return redirect('xomashyo:chiqimlar')

        yetkazib_beruvchi = None
        if yb_id:
            yetkazib_beruvchi = get_object_or_404(YetkazibBeruvchi, id=yb_id)

        with transaction.atomic():
            harakatlar_info = []

            for row in rows:
                xomashyo = get_object_or_404(Xomashyo, id=row['xomashyo_id'])
                miqdor   = Decimal(str(row['miqdor']))

                birlik_uzs = Decimal(str(row.get('birlik_narx_uzs') or xomashyo.narxi or 0))
                birlik_usd_str = row.get('birlik_narx_usd')
                birlik_usd = Decimal(str(birlik_usd_str)) if birlik_usd_str else None

                jami_uzs = birlik_uzs * miqdor
                jami_usd = (birlik_usd * miqdor) if birlik_usd else None

                # XomashyoHarakat yaratiladi — ombor yangilanadi
                harakat = XomashyoHarakat(
                    xomashyo=xomashyo,
                    harakat_turi='kirim',
                    miqdori=miqdor,
                    sana=sana,
                    birlik_narx_uzs=birlik_uzs,
                    birlik_narx_usd=birlik_usd,
                    jami_narx_uzs=jami_uzs,
                    jami_narx_usd=jami_usd,
                    usd_kurs=usd_kurs,
                    yetkazib_beruvchi=yetkazib_beruvchi,
                    foydalanuvchi=request.user,
                    izoh=izoh,
                    # tolov_holati → save() ichida 'tolanmagan' bo'ladi
                )
                harakat.save()  # ← bu yerda ombor yangilanadi, Chiqim EMAS

                harakatlar_info.append(
                    f"{xomashyo.nomi} {miqdor:g} {xomashyo.get_olchov_birligi_display()}"
                    f" ({jami_uzs:,.0f} so'm)"
                )

            msg = "✅ Xomashyo kirim saqlandi: " + ", ".join(harakatlar_info)
            msg += " | To'lov keyinroq amalga oshirilishi mumkin."
            messages.success(request, msg)

    except (decimal.InvalidOperation, TypeError, KeyError) as e:
        messages.error(request, f"Son formatida xatolik: {e}")
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")

    return redirect('xomashyo:chiqimlar')


# ─────────────────────────────────────────────────────────────────
# CHIQIM QO'SHISH  (to'lov yoki boshqa chiqim)
# ─────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def chiqim_qoshish(request):
    """
    chiqim_turi = 'xomashyo_tolov' | 'boshqa'

    --- xomashyo_tolov ---
    items JSON:
      [{
        "harakat_id":  5,        ← qaysi XomashyoHarakat uchun
        "miqdor_uzs":  60000,
        "miqdor_usd":  5.0,      (ixtiyoriy)
        "kurs":        12500,    (ixtiyoriy)
      }, ...]

    --- boshqa ---
    items JSON:
      [{"name": "Elektr", "narx": "120000", "category_id": 2}, ...]
    """
    if request.method != 'POST':
        return redirect('xomashyo:chiqimlar')

    chiqim_turi = request.POST.get('chiqim_turi')
    izoh        = request.POST.get('izoh', '').strip()
    sana        = _parse_sana(request.POST.get('sana'))
    if not sana:
        sana = timezone.now()
        
    try:
        rows = json.loads(request.POST.get('items', '[]'))
        if not rows:
            messages.error(request, "Kamida bitta qator kerak!")
            return redirect('xomashyo:chiqimlar')

        with transaction.atomic():

            # ── XOMASHYO TO'LOV ──────────────────────────────────
            if chiqim_turi == 'xomashyo_tolov':
                xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(
                    name="Xomashyo to'lovi"
                )
                jami_uzs     = Decimal('0')
                jami_usd     = Decimal('0')
                item_objects = []
                izoh_parts   = []

                for row in rows:
                    harakat    = get_object_or_404(XomashyoHarakat, id=row['harakat_id'])
                    miqdor_uzs = Decimal(str(row['miqdor_uzs']))
                    miqdor_usd_str = row.get('miqdor_usd')
                    miqdor_usd = Decimal(str(miqdor_usd_str)) if miqdor_usd_str else None
                    kurs_str   = row.get('kurs')
                    kurs       = Decimal(str(kurs_str)) if kurs_str else None

                    # Qoldiqdan oshmasligi kerak
                    if miqdor_uzs > harakat.qoldiq_uzs:
                        raise ValueError(
                            f"{harakat.xomashyo.nomi} uchun qoldiq: "
                            f"{harakat.qoldiq_uzs:,.0f} so'm, "
                            f"kiritilgan: {miqdor_uzs:,.0f} so'm"
                        )

                    jami_uzs += miqdor_uzs
                    if miqdor_usd:
                        jami_usd += miqdor_usd

                    olchov = harakat.xomashyo.get_olchov_birligi_display()
                    izoh_parts.append(
                        f"{harakat.xomashyo.nomi} ({harakat.miqdori:g} {olchov}) "
                        f"uchun {miqdor_uzs:,.0f} so'm"
                    )
                    item_objects.append({
                        'harakat':    harakat,
                        'miqdor_uzs': miqdor_uzs,
                        'miqdor_usd': miqdor_usd,
                        'kurs':       kurs,
                        'name': (
                            f"{harakat.xomashyo.nomi} to'lovi — "
                            f"{harakat.sana.strftime('%d.%m.%Y')}"
                        ),
                    })

                auto_izoh = "; ".join(izoh_parts)
                if izoh:
                    auto_izoh += f"\nIzoh: {izoh}"

                chiqim = Chiqim.objects.create(
                    name=f"Xomashyo to'lovi — {sana.strftime('%d.%m.%Y')}",
                    category=xomashyo_cat,
                    price=jami_uzs,
                    price_usd=jami_usd if jami_usd else None,
                    usd_kurs=item_objects[0]['kurs'] if item_objects else None,
                    izoh=auto_izoh,
                    created=sana,
                    created_by=request.user,
                )

                for obj in item_objects:
                    ChiqimItem.objects.create(
                        chiqim=chiqim,
                        item_turi='xomashyo',
                        name=obj['name'],
                        price_uzs=obj['miqdor_uzs'],
                        price_usd=obj['miqdor_usd'],
                        tolov_kursi=obj['kurs'],
                        xomashyo_harakat=obj['harakat'],
                        # ↑ save() ichida harakat.tolov_yangilash() chaqiriladi
                        # ↑ ombor O'ZGARMAYDI
                    )

                messages.success(
                    request,
                    f"✅ To'lov saqlandi: {auto_izoh} | Jami: {jami_uzs:,.0f} so'm"
                )

            # ── BOSHQA CHIQIM ────────────────────────────────────
            elif chiqim_turi == 'boshqa':
                jami_narx    = Decimal('0')
                item_objects = []

                for row in rows:
                    name   = row.get('name', '').strip()
                    narx   = Decimal(str(row['narx']))
                    cat_id = row.get('category_id') or None
                    cat    = ChiqimTuri.objects.get(id=cat_id) if cat_id else None
                    if not name or narx <= 0:
                        continue
                    jami_narx += narx
                    item_objects.append({'name': name, 'narx': narx, 'category': cat})

                if not item_objects:
                    messages.error(request, "To'g'ri ma'lumot kiriting!")
                    return redirect('xomashyo:chiqimlar')

                names_str = ", ".join(o['name'] for o in item_objects)
                chiqim = Chiqim.objects.create(
                    name=names_str,
                    category=item_objects[0]['category'],
                    price=jami_narx,
                    izoh=izoh,
                    created=sana,
                    created_by=request.user,
                )

                for obj in item_objects:
                    ChiqimItem.objects.create(
                        chiqim=chiqim,
                        item_turi='boshqa',
                        name=obj['name'],
                        price_uzs=obj['narx'],
                    )

                messages.success(
                    request,
                    f"✅ {names_str} — {jami_narx:,.0f} so'm | {sana}"
                )

            else:
                messages.error(request, "Chiqim turini tanlang!")

    except ValueError as e:
        messages.error(request, f"⚠️ {e}")
    except (decimal.InvalidOperation, TypeError) as e:
        messages.error(request, f"Son formatida xatolik: {e}")
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")

    return redirect('xomashyo:chiqimlar')


# ─────────────────────────────────────────────────────────────────
# CHIQIM O'CHIRISH
# ─────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def chiqim_ochirish(request, chiqim_id):
    """
    Chiqim o'chirilganda:
    - ChiqimItem.delete() → harakat.tolov_yangilash() avtomatik chaqiriladi
    - Ombor O'ZGARMAYDI
    """
    if request.method == 'POST':
        chiqim = get_object_or_404(Chiqim, id=chiqim_id)
        # cascade: ChiqimItem.delete() → harakat qayta hisoblanadi
        chiqim.delete()
        messages.success(request, "✅ Chiqim o'chirildi. To'lov holati yangilandi.")
    return redirect('xomashyo:chiqimlar')


# ─────────────────────────────────────────────────────────────────
# XOMASHYO KIRIM O'CHIRISH
# ─────────────────────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def xomashyo_kirim_ochirish(request, harakat_id):
    """
    Xomashyo kirim o'chirilganda:
    - Ombor qayta hisoblab KAMAYADI
    - Bog'liq ChiqimItemlar ham o'chiriladi (cascade)
    """
    if request.method != 'POST':
        return redirect('xomashyo:chiqimlar')

    harakat = get_object_or_404(XomashyoHarakat, id=harakat_id, harakat_turi='kirim')

    # Bog'liq to'lovlar bo'lsa ogohlantirish
    tolovlar_soni = harakat.tolovlar.count()
    if tolovlar_soni > 0 and not request.POST.get('tasdiqlash'):
        messages.warning(
            request,
            f"Bu kirimga {tolovlar_soni} ta to'lov bog'langan. "
            f"O'chirish uchun 'tasdiqlash' ni yuboring."
        )
        return redirect('xomashyo:chiqimlar')

    with transaction.atomic():
        xomashyo = harakat.xomashyo
        # Ombor qayta kamayadi
        if xomashyo and harakat.harakat_turi == 'kirim':
            xomashyo.miqdori -= harakat.miqdori
            xomashyo.save()
        harakat.delete()

    messages.success(request, "✅ Xomashyo kirimi o'chirildi.")
    return redirect('xomashyo:chiqimlar')


class XomashyolarListView(AdminRequiredMixin,ListView):
    model = Xomashyo
    template_name = 'xomashyo/xomashyo.html'
    context_object_name = 'xomashyolar'

    def get_queryset(self):
        queryset = Xomashyo.objects.select_related('category', 'yetkazib_beruvchi').all()
        category_filter = self.request.GET.get('category')

        if category_filter and category_filter != 'all':
            queryset = queryset.filter(category_id=category_filter)

        # Har bir xomashyo uchun jami chiqimni qo'shish
        xomashyolar_with_chiqim = []
        for xomashyo in queryset:
            jami_chiqim = XomashyoHarakat.objects.filter(
                xomashyo=xomashyo,
                harakat_turi='chiqim'
            ).aggregate(total=Sum('miqdori'))['total'] or 0
            xomashyo.jami_chiqim = jami_chiqim
            xomashyolar_with_chiqim.append(xomashyo)

        return xomashyolar_with_chiqim

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = Xomashyo.objects.all()

        context['categories'] = XomashyoCategory.objects.all()
        context['jami_xomashyolar'] = queryset.count()
        context['kam_qolganlar'] = queryset.filter(
            miqdori__lt=F('minimal_miqdor')
        ).count()
        context['muddati_otganlar'] = queryset.filter(holati='expired').count()
        context['jami_qiymat'] = sum(x.miqdori * (x.narxi or 0) for x in queryset)

        # Agar filter ishlashini xohlasangiz
        category_filter = self.request.GET.get('category')
        context['selected_category'] = category_filter or 'all'

        return context

class XomashyoDetailView(AdminRequiredMixin,DetailView):
    model = Xomashyo
    template_name = 'xomashyo/xomashyo_detail.html'
    context_object_name = 'xomashyo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        xomashyo = self.object

        harakat_filter = self.request.GET.get('harakat')
        harakatlar = XomashyoHarakat.objects.filter(xomashyo=xomashyo).select_related(
            'foydalanuvchi'
        )
        if harakat_filter and harakat_filter != 'all':
            harakatlar = harakatlar.filter(harakat_turi=harakat_filter)

        jami_kirim = XomashyoHarakat.objects.filter(
            xomashyo=xomashyo, harakat_turi='kirim'
        ).aggregate(total=Sum('miqdori'))['total'] or 0

        jami_chiqim = XomashyoHarakat.objects.filter(
            xomashyo=xomashyo, harakat_turi='chiqim'
        ).aggregate(total=Sum('miqdori'))['total'] or 0

        harakatlar_soni = harakatlar.count()

        context.update({
            'harakatlar': harakatlar.order_by('-sana'),
            'harakatlar_soni': harakatlar_soni,
            'jami_kirim': jami_kirim,
            'jami_chiqim': jami_chiqim,
            'harakat_filter': harakat_filter or 'all',
        })

        return context

@login_required(login_url="login")
@user_passes_test(is_admin,login_url='login')
def jarayon_xomashyo_hisobot(request):
    """
    Kroy, Zakatovka, Kosib kabi jarayon xomashyolari uchun hisob-kitob sahifasi
    """
    # Faqat jarayon tipidagi kategoriyalarni olish
    jarayon_categories = XomashyoCategory.objects.filter(turi='process')
    
    # Filtrlash
    selected_category = request.GET.get('category', 'all')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Asosiy query
    xomashyolar = Xomashyo.objects.filter(
        category__turi='process'
    ).select_related('category', 'yetkazib_beruvchi')
    
    if selected_category != 'all':
        xomashyolar = xomashyolar.filter(category_id=selected_category)
    
    xomashyo_list = []
    jami_kirim = 0
    jami_chiqim = 0
    jami_qoldiq = 0
    
    for xomashyo in xomashyolar:
        # Harakatlar query
        harakatlar_query = XomashyoHarakat.objects.filter(
            Q(xomashyo=xomashyo) | Q(xomashyo_variant__xomashyo=xomashyo)
        )
        
        if date_from:
            harakatlar_query = harakatlar_query.filter(
                sana__gte=datetime.strptime(date_from, '%Y-%m-%d')
            )
        if date_to:
            harakatlar_query = harakatlar_query.filter(
                sana__lte=datetime.strptime(date_to, '%Y-%m-%d')
            )
        
        # Kirim va chiqim hisoblash
        kirim = harakatlar_query.filter(
            harakat_turi='kirim'
        ).aggregate(
            jami=Coalesce(Sum('miqdori'), 0, output_field=DecimalField())
        )['jami']
        
        chiqim = harakatlar_query.filter(
            harakat_turi='chiqim'
        ).aggregate(
            jami=Coalesce(Sum('miqdori'), 0, output_field=DecimalField())
        )['jami']
        
        qoldiq = xomashyo.miqdori
        jami_summa = qoldiq * (xomashyo.narxi or 0)
        
        xomashyo_list.append({
            'xomashyo': xomashyo,
            'kirim': kirim,
            'chiqim': chiqim,
            'qoldiq': qoldiq,
            'jami_summa': jami_summa,
            'oxirgi_harakatlar': harakatlar_query.order_by('-sana')[:5]
        })
        
        jami_kirim += kirim
        jami_chiqim += chiqim
        jami_qoldiq += qoldiq
    
    eng_kop_ishlatilgan = sorted(
        xomashyo_list, 
        key=lambda x: x['chiqim'], 
        reverse=True
    )[:5]
    
    context = {
        'jarayon_categories': jarayon_categories,
        'selected_category': selected_category,
        'date_from': date_from,
        'date_to': date_to,
        'xomashyo_list': xomashyo_list,
        'jami_kirim': jami_kirim,
        'jami_chiqim': jami_chiqim,
        'jami_qoldiq': jami_qoldiq,
        'eng_kop_ishlatilgan': eng_kop_ishlatilgan,
        'jami_xomashyolar': len(xomashyo_list),
    }
    
    return render(request, 'xomashyo/jarayon_hisobot.html', context)


class YetkazibBeruvchilarView(AdminRequiredMixin, ListView):
    model = YetkazibBeruvchi
    template_name = 'yetkazib_beruvchi/list.html'
    context_object_name = 'yetkazib_beruvchilar'
 
    def get_queryset(self):
        qs = YetkazibBeruvchi.objects.all().order_by('nomi')
        for yb in qs:
            harakatlar = XomashyoHarakat.objects.filter(
                yetkazib_beruvchi=yb,
                harakat_turi='kirim',
                tolov_holati__in=['tolanmagan', 'qisman']
            )
            yb.jami_qarz_uzs = sum(h.qoldiq_uzs for h in harakatlar)
        return qs
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = ctx['yetkazib_beruvchilar']
        ctx['qarzli_count']  = sum(1 for yb in qs if yb.jami_qarz_uzs > 0)
        ctx['umumiy_qarz']   = sum(yb.jami_qarz_uzs for yb in qs)
        return ctx
 
 
# ─────────────────────────────────────────────────────────────────
# YETKAZIB BERUVCHI DETAIL
# ─────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def yetkazib_beruvchi_detail(request, yb_id):
    yb = get_object_or_404(YetkazibBeruvchi, id=yb_id)
 
    # Qarzli harakatlar — eng eski birinchi (FIFO uchun)
    qarzdor_harakatlar = XomashyoHarakat.objects.filter(
        yetkazib_beruvchi=yb,
        harakat_turi='kirim',
        tolov_holati__in=['tolanmagan', 'qisman']
    ).select_related('xomashyo').order_by('sana', 'id')
 
    # To'liq to'langan tarix
    toliq_harakatlar = XomashyoHarakat.objects.filter(
        yetkazib_beruvchi=yb,
        harakat_turi='kirim',
        tolov_holati='toliq'
    ).select_related('xomashyo').order_by('-sana')[:20]
 
    jami_qarz_uzs = sum(h.qoldiq_uzs for h in qarzdor_harakatlar)
    jami_qarz_usd = sum(h.qoldiq_usd or 0 for h in qarzdor_harakatlar)
 
    # Oxirgi to'lovlar
    oxirgi_tolovlar = ChiqimItem.objects.filter(
        xomashyo_harakat__yetkazib_beruvchi=yb,
        item_turi='xomashyo'
    ).select_related(
        'chiqim',
        'xomashyo_harakat__xomashyo'
    ).order_by('-chiqim__created')[:15]
 
    # ── qarzdor_json — JS FIFO preview uchun ──────────────────────
    # MUHIM: field nomlari JS bilan mos bo'lishi kerak
    # JS da ishlatiladi: h.nomi, h.sana, h.qoldiq_uzs, h.qoldiq_usd
    qarzdor_json_list = []
    for h in qarzdor_harakatlar:
        qarzdor_json_list.append({
            'id':           str(h.id),
            'nomi':         h.xomashyo.nomi if h.xomashyo else '—',       # JS: h.nomi
            'sana':         h.sana.strftime('%d.%m.%Y') if h.sana else '', # JS: h.sana
            'miqdori':      float(h.miqdori),
            'olchov':       h.xomashyo.get_olchov_birligi_display() if h.xomashyo else '',
            'jami_uzs':     float(h.jami_narx_uzs),
            'jami_usd':     float(h.jami_narx_usd or 0),
            'tolangan_uzs': float(h.tolangan_uzs),
            'qoldiq_uzs':   float(h.qoldiq_uzs),                          # JS: h.qoldiq_uzs
            'qoldiq_usd':   float(h.qoldiq_usd or 0),
            'usd_kurs':     float(h.usd_kurs or 0),
            'foiz':         h.tolov_foizi,
        })
 
    context = {
        'yb':                   yb,
        'qarzdor_harakatlar':   qarzdor_harakatlar,
        'toliq_harakatlar':     toliq_harakatlar,
        'jami_qarz_uzs':        jami_qarz_uzs,
        'jami_qarz_usd':        jami_qarz_usd,
        'oxirgi_tolovlar':      oxirgi_tolovlar,
        'today_str':            date.today().strftime('%Y-%m-%d'),
        'qarzdor_json':         json.dumps(qarzdor_json_list, cls=DjangoJSONEncoder),
    }
    return render(request, 'yetkazib_beruvchi/detail.html', context)
 
 
# ─────────────────────────────────────────────────────────────────
# AVTOMATIK TAQSIMLASH (FIFO)
# ─────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def yb_avto_tolov(request, yb_id):
    if request.method != 'POST':
        return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
    yb      = get_object_or_404(YetkazibBeruvchi, id=yb_id)
    sana    = _parse_sana(request.POST.get('sana'))
    valyuta = request.POST.get('valyuta', 'uzs')
    izoh    = request.POST.get('izoh', '').strip()
 
    try:
        summa_str = request.POST.get('summa', '').replace(' ', '').replace(',', '')
        summa     = Decimal(summa_str)
        if summa <= 0:
            raise ValueError("Summa 0 dan katta bo'lishi kerak!")
    except (decimal.InvalidOperation, ValueError) as e:
        messages.error(request, f"⚠️ Summa noto'g'ri: {e}")
        return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
    kurs_str = request.POST.get('usd_kurs', '').strip()
    try:
        usd_kurs = Decimal(kurs_str) if kurs_str else None
    except decimal.InvalidOperation:
        usd_kurs = None
 
    if valyuta == 'usd' and not usd_kurs:
        messages.error(request, "⚠️ USD to'lov uchun kurs kiritilishi shart!")
        return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
    # UZS ekvivalenti
    if valyuta == 'usd':
        summa_uzs = (summa * usd_kurs).quantize(Decimal('1'), rounding=ROUND_DOWN)
        summa_usd = summa
    else:
        summa_uzs = summa
        summa_usd = (summa / usd_kurs).quantize(Decimal('0.0001'), rounding=ROUND_DOWN) if usd_kurs else None
 
    # FIFO harakatlar
    qarzdor_harakatlar = XomashyoHarakat.objects.filter(
        yetkazib_beruvchi=yb,
        harakat_turi='kirim',
        tolov_holati__in=['tolanmagan', 'qisman']
    ).select_related('xomashyo').order_by('sana', 'id')
 
    jami_qarz = sum(h.qoldiq_uzs for h in qarzdor_harakatlar)
    if summa_uzs > jami_qarz:
        messages.error(
            request,
            f"⚠️ Kiritilgan summa ({summa_uzs:,.0f} so'm) "
            f"jami qarzdan ({jami_qarz:,.0f} so'm) ko'p!"
        )
        return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
    try:
        with transaction.atomic():
            xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(name="Xomashyo to'lovi")
 
            qolgan_uzs   = summa_uzs
            item_objects = []
            izoh_parts   = []
 
            for harakat in qarzdor_harakatlar:
                if qolgan_uzs <= 0:
                    break
 
                qoldiq = harakat.qoldiq_uzs
                if qoldiq <= 0:
                    continue
 
                tolov_uzs = min(qolgan_uzs, qoldiq)
                is_toliq  = (tolov_uzs >= qoldiq)
 
                # USD — kurs farqi tiyinlarini yo'q qilish:
                # To'liq to'lovda harakatning aniq qoldiq_usd ishlatiladi
                if harakat.jami_narx_usd and harakat.qoldiq_usd:
                    if is_toliq:
                        tolov_usd = harakat.qoldiq_usd  # Aniq, hisoblashsiz
                    else:
                        nisbat    = tolov_uzs / qoldiq
                        tolov_usd = (harakat.qoldiq_usd * nisbat).quantize(
                            Decimal('0.0001'), rounding=ROUND_DOWN
                        )
                else:
                    tolov_usd = None
 
                qolgan_uzs -= tolov_uzs
 
                nomi   = harakat.xomashyo.nomi if harakat.xomashyo else '—'
                olchov = harakat.xomashyo.get_olchov_birligi_display() if harakat.xomashyo else ''
                sana_str = harakat.sana.strftime('%d.%m.%Y') if harakat.sana else ''
 
                izoh_parts.append(f"{nomi} ({sana_str}) — {tolov_uzs:,.0f} so'm")
                item_objects.append({
                    'harakat':   harakat,
                    'tolov_uzs': tolov_uzs,
                    'tolov_usd': tolov_usd,
                    'name':      f"{nomi} to'lovi — {sana_str}",
                })
 
            if not item_objects:
                messages.error(request, "Taqsimlanadigan qarz topilmadi!")
                return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
            auto_izoh = "; ".join(izoh_parts)
            if izoh:
                auto_izoh += f"\nIzoh: {izoh}"
 
            chiqim = Chiqim.objects.create(
                name=f"Xomashyo to'lovi — {yb.nomi} — {sana.strftime('%d.%m.%Y')}",
                category=xomashyo_cat,
                price=summa_uzs,
                price_usd=summa_usd,
                usd_kurs=usd_kurs,
                izoh=auto_izoh,
                created=sana,
                created_by=request.user,
            )
 
            for obj in item_objects:
                ChiqimItem.objects.create(
                    chiqim=chiqim,
                    item_turi='xomashyo',
                    name=obj['name'],
                    price_uzs=obj['tolov_uzs'],
                    price_usd=obj['tolov_usd'],
                    tolov_kursi=usd_kurs,
                    xomashyo_harakat=obj['harakat'],
                )
 
            messages.success(
                request,
                f"✅ {summa_uzs:,.0f} so'm — {len(item_objects)} ta harakatga taqsimlandi."
            )
 
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")
 
    return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
 
# ─────────────────────────────────────────────────────────────────
# ALOHIDA HARAKAT UCHUN TO'LOV
# ─────────────────────────────────────────────────────────────────
@login_required(login_url='login')
@user_passes_test(lambda u: u.is_staff, login_url='login')
def yb_harakat_tolov(request, yb_id, harakat_id):
    if request.method != 'POST':
        return redirect('xomashyo:yb_detail', yb_id=yb_id)
 
    harakat = get_object_or_404(
        XomashyoHarakat,
        id=harakat_id,
        yetkazib_beruvchi_id=yb_id,
        harakat_turi='kirim',
    )
 
    sana    = _parse_sana(request.POST.get('sana'))
    valyuta = request.POST.get('valyuta', 'uzs')
    toliq   = request.POST.get('toliq') == '1'
    izoh    = request.POST.get('izoh', '').strip()
 
    kurs_str = request.POST.get('usd_kurs', '').strip()
    try:
        usd_kurs = Decimal(kurs_str) if kurs_str else None
    except decimal.InvalidOperation:
        usd_kurs = None
 
    try:
        if toliq:
            # To'liq to'lov — aniq raqamlar, hisoblashsiz
            tolov_uzs = harakat.qoldiq_uzs
            tolov_usd = harakat.qoldiq_usd  # None bo'lishi mumkin
        else:
            summa_str = request.POST.get('summa', '').replace(' ', '').replace(',', '')
            summa     = Decimal(summa_str)
 
            if valyuta == 'usd':
                if not usd_kurs:
                    raise ValueError("USD to'lov uchun kurs kiritilishi shart!")
                tolov_uzs = (summa * usd_kurs).quantize(Decimal('1'), rounding=ROUND_DOWN)
                tolov_usd = summa
            else:
                tolov_uzs = summa
                # USD ekvivalent — faqat harakat USD li bo'lsa
                if usd_kurs and harakat.jami_narx_usd:
                    tolov_usd = (summa / usd_kurs).quantize(
                        Decimal('0.0001'), rounding=ROUND_DOWN
                    )
                else:
                    tolov_usd = None
 
        if tolov_uzs <= 0:
            raise ValueError("To'lov summasi 0 dan katta bo'lishi kerak!")
        if tolov_uzs > harakat.qoldiq_uzs:
            raise ValueError(
                f"To'lov ({tolov_uzs:,.0f}) qoldiqdan ({harakat.qoldiq_uzs:,.0f} so'm) ko'p!"
            )
 
        with transaction.atomic():
            xomashyo_cat, _ = ChiqimTuri.objects.get_or_create(name="Xomashyo to'lovi")
            nomi   = harakat.xomashyo.nomi if harakat.xomashyo else '—'
            olchov = harakat.xomashyo.get_olchov_birligi_display() if harakat.xomashyo else ''
            sana_str = harakat.sana.strftime('%d.%m.%Y') if harakat.sana else ''
 
            chiqim = Chiqim.objects.create(
                name=f"{nomi} to'lovi — {sana.strftime('%d.%m.%Y')}",
                category=xomashyo_cat,
                price=tolov_uzs,
                price_usd=tolov_usd,
                usd_kurs=usd_kurs,
                izoh=izoh or f"{nomi} ({harakat.miqdori:g} {olchov}) — {sana_str}",
                created=sana,
                created_by=request.user,
            )
            ChiqimItem.objects.create(
                chiqim=chiqim,
                item_turi='xomashyo',
                name=f"{nomi} to'lovi — {sana_str}",
                price_uzs=tolov_uzs,
                price_usd=tolov_usd,
                tolov_kursi=usd_kurs,
                xomashyo_harakat=harakat,
            )
 
            messages.success(
                request,
                f"✅ {nomi} uchun {tolov_uzs:,.0f} so'm to'lov saqlandi."
                + (" ✔ To'liq to'landi!" if harakat.tolov_holati == 'toliq' else "")
            )
 
    except ValueError as e:
        messages.error(request, f"⚠️ {e}")
    except (decimal.InvalidOperation, TypeError) as e:
        messages.error(request, f"Son formati xato: {e}")
    except Exception as e:
        messages.error(request, f"❌ Xatolik: {e}")
 
    return redirect('xomashyo:yb_detail', yb_id=yb_id)


 