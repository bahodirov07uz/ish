#xomashyo app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView,DetailView,View
from django.db.models import Sum,F,DecimalField, Q
from datetime import date,datetime
import decimal
from decimal import Decimal
from django.db import transaction
from django.contrib.auth.decorators import login_required,user_passes_test
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.utils.decorators import method_decorator

from django.db.models.functions import Coalesce
from crm.models import Chiqim, ChiqimTuri,Ishchi,ChiqimItem
from xomashyo.models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi,XomashyoCategory,Taminlash,TaminlashItem,XomashyoVariant
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


class TaminlashView(AdminRequiredMixin,View):
    """Taminlashlar ro'yxati va boshqaruv"""
    template_name = 'taminlash/taminlash.html'

    def get(self, request, *args, **kwargs):
        """GET so'rov - taminlashlar ro'yxati"""
        
        # Filtrlar
        ishchi_id = request.GET.get('ishchi')
        status = request.GET.get('status')
        sana_from = request.GET.get('sana_from')
        sana_to = request.GET.get('sana_to')
        search = request.GET.get('search', '').strip()
        
        # Asosiy query
        taminlashlar = Taminlash.objects.select_related(
            'ishchi', 'yaratuvchi'
        ).prefetch_related('items__xomashyo', 'items__variant').all()
        
        # Filtr: Ishchi
        if ishchi_id:
            taminlashlar = taminlashlar.filter(ishchi_id=ishchi_id)
        
        # Filtr: Status
        if status:
            taminlashlar = taminlashlar.filter(status=status)
        
        # Filtr: Sana oralig'i
        if sana_from:
            taminlashlar = taminlashlar.filter(sana__gte=sana_from)
        if sana_to:
            taminlashlar = taminlashlar.filter(sana__lte=sana_to)
        
        # Qidiruv
        if search:
            taminlashlar = taminlashlar.filter(
                Q(ishchi__ism__icontains=search) |
                Q(izoh__icontains=search) |
                Q(items__xomashyo__nomi__icontains=search)
            ).distinct()
        
        # Statistika
        stats = {
            'jami': taminlashlar.count(),
            'aktiv': taminlashlar.filter(status='aktiv').count(),
            'qaytarilgan': taminlashlar.filter(status='qaytarilgan').count(),
            'yakunlangan': taminlashlar.filter(status='yakunlangan').count(),
        }
        
        # Ishchilar ro'yxati (filtr uchun)
        ishchilar = Ishchi.objects.filter(
            is_oylik_open=True
        ).order_by('ism')
        
        context = {
            'taminlashlar': taminlashlar.order_by('-sana', '-id')[:100],  # Oxirgi 100 ta
            'ishchilar': ishchilar,
            'stats': stats,
            'filters': {
                'ishchi_id': ishchi_id,
                'status': status,
                'sana_from': sana_from,
                'sana_to': sana_to,
                'search': search,
            }
        }
        
        return render(request, self.template_name, context)


class TaminlashQaytarishView(AdminRequiredMixin,View):
    """Taminlashni qaytarish"""
    
    def post(self, request, taminlash_id, *args, **kwargs):
        """POST so'rov - taminlashni qaytarish"""
        
        try:
            with transaction.atomic():
                taminlash = get_object_or_404(
                    Taminlash.objects.select_related('ishchi').prefetch_related('items'),
                    id=taminlash_id
                )
                
                # Status tekshirish
                if taminlash.status == 'qaytarilgan':
                    messages.warning(request, "⚠️ Bu taminlash allaqachon qaytarilgan!")
                    return redirect('xomashyo:taminlash')
                
                # Har bir item uchun qolgan miqdorni qaytarish
                qaytarilgan_items = []
                for item in taminlash.items.all():
                    if item.qolgan > 0:
                        # Omborga qaytarish
                        if item.variant:
                            item.variant.miqdori += item.qolgan
                            item.variant.save(update_fields=['miqdori'])
                        else:
                            item.xomashyo.miqdori += item.qolgan
                            item.xomashyo.save(update_fields=['miqdori', 'updated_at'])
                        
                        # Ishlatilgan va qolgan yangilash
                        item.ishlatilgan += item.qolgan
                        qaytarilgan_miqdor = item.qolgan
                        item.qolgan = 0
                        item.save(update_fields=['ishlatilgan', 'qolgan'])
                        
                        qaytarilgan_items.append({
                            'nomi': item.xomashyo.nomi,
                            'miqdor': qaytarilgan_miqdor,
                            'olchov': item.xomashyo.get_olchov_birligi_display()
                        })
                
                # Taminlash statusini o'zgartirish
                taminlash.status = 'qaytarilgan'
                taminlash.qaytarilgan_sana = datetime.now()
                taminlash.save(update_fields=['status', 'qaytarilgan_sana'])
                
                # Success message
                if qaytarilgan_items:
                    msg = f"✅ {taminlash.ishchi.ism}ning taminlashi qaytarildi!\n\n"
                    msg += "🔄 Qaytarilgan xomashyolar:\n"
                    for item in qaytarilgan_items:
                        msg += f"   • {item['nomi']}: +{item['miqdor']} {item['olchov']}\n"
                    messages.success(request, msg)
                else:
                    messages.info(request, "ℹ️ Qaytariladigan xomashyo topilmadi (barchasi ishlatilgan)")
                
        except Taminlash.DoesNotExist:
            messages.error(request, "❌ Taminlash topilmadi!")
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return redirect('xomashyo:taminlash')



@method_decorator(login_required, name='dispatch')
class TaminlashDetailView(AdminRequiredMixin,View):
    """Taminlash tafsilotlari"""
    template_name = 'taminlash/taminlash_detail.html'
    
    def get(self, request, taminlash_id, *args, **kwargs):
        """GET so'rov - taminlash tafsilotlari"""
        
        taminlash = get_object_or_404(
            Taminlash.objects.select_related(
                'ishchi', 'ishchi__turi', 'yaratuvchi'
            ).prefetch_related(
                'items__xomashyo__category',
                'items__variant'
            ),
            id=taminlash_id
        )
        
        # Statistika
        items = taminlash.items.all()
        stats = {
            'jami_xomashyolar': items.count(),
            'jami_berilgan': sum(item.miqdor for item in items),
            'jami_ishlatilgan': sum(item.ishlatilgan for item in items),
            'jami_qolgan': sum(item.qolgan for item in items),
            'jami_summa': taminlash.jami_summa() if hasattr(taminlash, 'jami_summa') else 0,
        }
        
        context = {
            'taminlash': taminlash,
            'items': items,
            'stats': stats,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class TaminlashQushishView(AdminRequiredMixin,View):
    """Yangi taminlash yaratish"""
    template_name = 'taminlash/taminlash_qoshish.html'
    
    def get(self, request, *args, **kwargs):
        """GET so'rov - forma ko'rsatish"""
        
        ishchilar = Ishchi.objects.filter(
            is_oylik_open=True
        ).select_related('turi').order_by('ism')
        
        # Faqat real xomashyolar (teri, astar, padoj)
        xomashyolar = Xomashyo.objects.filter(
            category__turi='real',
            holati='active',
            miqdori__gt=0
        ).select_related('category').prefetch_related('variantlar').order_by('category__name', 'nomi')
        
        context = {
            'ishchilar': ishchilar,
            'xomashyolar': xomashyolar,
            'today': datetime.now().date().isoformat(),
        }
        
        return render(request, self.template_name, context)
    
    def post(self, request, *args, **kwargs):
        """POST so'rov - taminlash yaratish"""
        
        ishchi_id = request.POST.get('ishchi')
        sana = request.POST.get('sana')
        izoh = request.POST.get('izoh', '')
        
        # Xomashyolar (multiple POST fields)
        xomashyo_ids = request.POST.getlist('xomashyo_id[]')
        variant_ids = request.POST.getlist('variant_id[]')
        miqdorlar = request.POST.getlist('miqdor[]')
        narxlar = request.POST.getlist('narx[]')
        
        try:
            with transaction.atomic():
                # Validatsiya
                if not ishchi_id:
                    raise ValueError("❌ Ishchi tanlanmagan!")
                
                if not xomashyo_ids or not any(xomashyo_ids):
                    raise ValueError("❌ Kamida bitta xomashyo tanlang!")
                
                ishchi = Ishchi.objects.get(id=ishchi_id)
                
                # Sana
                if sana:
                    try:
                        sana_obj = datetime.strptime(sana, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError("❌ Sana formati noto'g'ri!")
                else:
                    sana_obj = datetime.now().date()
                
                # Taminlash yaratish
                taminlash = Taminlash.objects.create(
                    ishchi=ishchi,
                    sana=sana_obj,
                    status='aktiv',
                    izoh=izoh,
                    yaratuvchi=request.user
                )
                
                for i in taminlash.items.all():
                    XomashyoHarakat.objects.create(
                        xomashyo=i.xomashyo,
                        harakat_turi = "taminlash",
                        miqdori=i.miqdor,
                        sana=sana,
                        foydalanuvchi=request.user,
                        izoh=f"{ishchi} ga {taminlash.jami_summa()} xomashyo taminlandi"
                    )
                    
                # Items yaratish
                created_items = []
                for i, xomashyo_id in enumerate(xomashyo_ids):
                    if not xomashyo_id:
                        continue
                    
                    variant_id = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                    
                    try:
                        miqdor = Decimal(miqdorlar[i]) if i < len(miqdorlar) and miqdorlar[i] else Decimal('0')
                    except (ValueError, IndexError):
                        continue
                    
                    if miqdor <= 0:
                        continue
                    
                    try:
                        narx = Decimal(narxlar[i]) if i < len(narxlar) and narxlar[i] else None
                    except (ValueError, IndexError):
                        narx = None
                    
                    xomashyo = Xomashyo.objects.get(id=xomashyo_id)
                    variant = XomashyoVariant.objects.get(id=variant_id) if variant_id else None
                    
                    # TaminlashItem yaratish (save metodida xomashyo miqdori kamayadi)
                    item = TaminlashItem.objects.create(
                        taminlash=taminlash,
                        xomashyo=xomashyo,
                        variant=variant,
                        miqdor=miqdor,
                        narx=narx
                    )
                    
                for i in taminlash.items.all():
                    XomashyoHarakat.objects.create(
                        xomashyo=i.xomashyo,
                        harakat_turi = "taminlash",
                        miqdori=i.miqdor,
                        sana=sana,
                        foydalanuvchi=request.user,
                        izoh=f"{ishchi} ga {taminlash.jami_summa()} xomashyo taminlandi"
                    )
                    
                    created_items.append({
                        'nomi': xomashyo.nomi,
                        'miqdor': miqdor,
                        'olchov': xomashyo.get_olchov_birligi_display(),
                        'variant': variant.rang if variant else None
                    })
                
                if not created_items:
                    raise ValueError("❌ Hech qanday xomashyo qo'shilmadi!")
                
                # Success message
                msg = f"✅ {ishchi.ism}ga ta'minlash berildi!\n\n"
                msg += "📦 Berilgan xomashyolar:\n"
                for item in created_items:
                    variant_info = f" ({item['variant']})" if item['variant'] else ""
                    msg += f"   • {item['nomi']}{variant_info}: {item['miqdor']} {item['olchov']}\n"
                msg += f"\n📅 Sana: {sana_obj.strftime('%d.%m.%Y')}"
                
                messages.success(request, msg)
                return redirect('xomashyo:taminlash_detail', taminlash_id=taminlash.id)
                
        except Ishchi.DoesNotExist:
            messages.error(request, "❌ Ishchi topilmadi!")
        except Xomashyo.DoesNotExist:
            messages.error(request, "❌ Xomashyo topilmadi!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return redirect('xomashyo:taminlash_qoshish')


@method_decorator(login_required, name='dispatch')
class TaminlashQaytarishView(AdminRequiredMixin,View):
    """Taminlashni qaytarish"""
    
    def post(self, request, taminlash_id, *args, **kwargs):
        """POST so'rov - taminlashni qaytarish"""
        
        try:
            with transaction.atomic():
                taminlash = get_object_or_404(
                    Taminlash.objects.select_related('ishchi').prefetch_related(
                        'items__xomashyo', 'items__variant'
                    ),
                    id=taminlash_id
                )
                
                # Status tekshirish
                if taminlash.status == 'qaytarilgan':
                    messages.warning(request, "⚠️ Bu ta'minlash allaqachon qaytarilgan!")
                    return redirect('xomashyo:taminlash_detail', taminlash_id=taminlash_id)
                
                # Har bir item uchun qolgan miqdorni qaytarish
                qaytarilgan_items = []
                jami_qaytarilgan = Decimal('0')
                
                for item in taminlash.items.all():
                    if item.qolgan > 0:
                        # Omborga qaytarish
                        if item.variant:
                            item.variant.miqdori += item.qolgan
                            item.variant.save(update_fields=['miqdori'])
                        else:
                            item.xomashyo.miqdori += item.qolgan
                            item.xomashyo.save(update_fields=['miqdori', 'updated_at'])
                        
                        # Ishlatilgan va qolgan yangilash
                        qaytarilgan_miqdor = item.qolgan
                        item.ishlatilgan += item.qolgan
                        item.qolgan = Decimal('0')
                        item.save(update_fields=['ishlatilgan', 'qolgan'])
                        
                        jami_qaytarilgan += qaytarilgan_miqdor
                        
                        variant_info = f" ({item.variant.rang})" if item.variant else ""
                        qaytarilgan_items.append({
                            'nomi': item.xomashyo.nomi + variant_info,
                            'miqdor': qaytarilgan_miqdor,
                            'olchov': item.xomashyo.get_olchov_birligi_display()
                        })
                
                # Taminlash statusini o'zgartirish
                taminlash.status = 'qaytarilgan'
                taminlash.qaytarilgan_sana = datetime.now()
                taminlash.save(update_fields=['status', 'qaytarilgan_sana'])
                
                # Success message
                if qaytarilgan_items:
                    msg = f"✅ {taminlash.ishchi.ism}ning ta'minlashi qaytarildi!\n\n"
                    msg += "🔄 Qaytarilgan xomashyolar:\n"
                    for item in qaytarilgan_items:
                        msg += f"   • {item['nomi']}: +{item['miqdor']} {item['olchov']}\n"
                    msg += f"\n📅 Qaytarilgan sana: {taminlash.qaytarilgan_sana.strftime('%d.%m.%Y %H:%M')}"
                    messages.success(request, msg)
                else:
                    messages.info(request, "ℹ️ Qaytariladigan xomashyo topilmadi (barchasi ishlatilgan)")
                
        except Taminlash.DoesNotExist:
            messages.error(request, "❌ Ta'minlash topilmadi!")
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return redirect('xomashyo:taminlash_detail', taminlash_id=taminlash_id)


@method_decorator(login_required, name='dispatch')
class TaminlashItemQaytarishView(AdminRequiredMixin,View):
    """Bitta item qaytarish (qisman qaytarish)"""
    
    def post(self, request, item_id, *args, **kwargs):
        """POST so'rov - itemni qaytarish"""
        
        qaytariladigan_miqdor_str = request.POST.get('qaytariladigan_miqdor')
        
        try:
            with transaction.atomic():
                item = get_object_or_404(
                    TaminlashItem.objects.select_related(
                        'taminlash__ishchi', 'xomashyo', 'variant'
                    ),
                    id=item_id
                )
                
                # Status tekshirish
                if item.taminlash.status == 'qaytarilgan':
                    messages.warning(request, "⚠️ Bu ta'minlash allaqachon qaytarilgan!")
                    return redirect('xomashyo:taminlash_detail', taminlash_id=item.taminlash.id)
                
                # Miqdorni tekshirish
                try:
                    qaytariladigan_miqdor = Decimal(qaytariladigan_miqdor_str)
                except (ValueError, TypeError):
                    raise ValueError("❌ Qaytariladigan miqdor noto'g'ri!")
                
                if qaytariladigan_miqdor <= 0:
                    raise ValueError("❌ Qaytariladigan miqdor 0 dan katta bo'lishi kerak!")
                
                if qaytariladigan_miqdor > item.qolgan:
                    raise ValueError(
                        f"❌ Qaytariladigan miqdor qolgan miqdordan katta! "
                        f"Qolgan: {item.qolgan}, Qaytariladigan: {qaytariladigan_miqdor}"
                    )
                
                # Omborga qaytarish
                if item.variant:
                    item.variant.miqdori += qaytariladigan_miqdor
                    item.variant.save(update_fields=['miqdori'])
                else:
                    item.xomashyo.miqdori += qaytariladigan_miqdor
                    item.xomashyo.save(update_fields=['miqdori', 'updated_at'])
                
                # Item yangilash
                item.ishlatilgan += (item.qolgan - qaytariladigan_miqdor)
                item.qolgan -= qaytariladigan_miqdor
                item.save(update_fields=['ishlatilgan', 'qolgan'])
                
                # Agar barcha itemlar qaytarilgan bo'lsa, taminlashni qaytarilgan qilish
                taminlash = item.taminlash
                if all(i.qolgan == 0 for i in taminlash.items.all()):
                    taminlash.status = 'qaytarilgan'
                    taminlash.qaytarilgan_sana = datetime.now()
                    taminlash.save(update_fields=['status', 'qaytarilgan_sana'])
                
                variant_info = f" ({item.variant.rang})" if item.variant else ""
                messages.success(
                    request,
                    f"✅ {item.xomashyo.nomi}{variant_info} qaytarildi: "
                    f"+{qaytariladigan_miqdor} {item.xomashyo.get_olchov_birligi_display()}"
                )
                
        except TaminlashItem.DoesNotExist:
            messages.error(request, "❌ Item topilmadi!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
            import traceback
            print(traceback.format_exc())
        
        return redirect('xomashyo:taminlash_detail', taminlash_id=item.taminlash.id)
