#xomashyo app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView,DetailView
from django.urls import reverse_lazy
from django.db.models import Sum,F,DecimalField, ExpressionWrapper,Q
from datetime import date,datetime, timedelta
from decimal import Decimal

from django.db.models.functions import Coalesce
from crm.models import Chiqim, ChiqimTuri
from .models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi,XomashyoCategory
from crm.views import AdminRequiredMixin

class ChiqimListView(AdminRequiredMixin,ListView):
    """Chiqimlar ro'yxati va yangi chiqim qo'shish"""
    model = Chiqim
    template_name = 'chiqim.html'
    context_object_name = 'chiqimlar'
    ordering = ['-created']
    paginate_by = 50
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        # Statistika
        context['bugungi_chiqim'] = Chiqim.objects.filter(
            created=today
        ).aggregate(Sum('price'))['price__sum'] or 0
        
        context['oylik_chiqim'] = Chiqim.objects.filter(
            created__year=today.year,
            created__month=today.month
        ).aggregate(Sum('price'))['price__sum'] or 0
        
        context['jami_chiqim'] = Chiqim.objects.aggregate(
            Sum('price')
        )['price__sum'] or 0
        
        # Form uchun ma'lumotlar
        context['xomashyolar'] = Xomashyo.objects.filter(
            holati='active'
        ).order_by('nomi')
        
        context['chiqim_turlari'] = ChiqimTuri.objects.all()
        context['yetkazib_beruvchilar'] = YetkazibBeruvchi.objects.all()
        
        return context


def chiqim_qoshish(request):
    """Yangi chiqim qo'shish"""
    if request.method == 'POST':
        chiqim_turi = request.POST.get('chiqim_turi')
        
        try:
            if chiqim_turi == 'xomashyo':
                # Xomashyo sotib olish
                xomashyo_id = request.POST.get('xomashyo')
                miqdor = request.POST.get('miqdor')
                narx = request.POST.get('xomashyo_narx')
                yetkazib_beruvchi_id = request.POST.get('yetkazib_beruvchi')
                izoh = request.POST.get('izoh', '')
                
                # Validatsiya
                if not xomashyo_id:
                    messages.error(request, 'Xomashyoni tanlang!')
                    return redirect('crm:chiqimlar')
                
                if not miqdor or Decimal(miqdor) <= 0:
                    messages.error(request, 'Miqdorni to\'g\'ri kiriting!')
                    return redirect('crm:chiqimlar')
                
                xomashyo = get_object_or_404(Xomashyo, id=xomashyo_id)
                miqdor_decimal = Decimal(miqdor)
                
                # Narxni hisoblash
                if narx:
                    narx_decimal = Decimal(narx)
                else:
                    # Agar narx kiritilmagan bo'lsa, xomashyoning narxidan hisoblash
                    narx_decimal = xomashyo.narxi * miqdor_decimal
                
                # Yetkazib beruvchi
                yetkazib_beruvchi = None
                if yetkazib_beruvchi_id:
                    yetkazib_beruvchi = YetkazibBeruvchi.objects.get(id=yetkazib_beruvchi_id)
                
                # XomashyoHarakat yaratish
                # Bu avtomatik ravishda:
                # 1. Chiqim obyektini yaratadi (save metodida)
                # 2. Xomashyo miqdorini yangilaydi (signal orqali)
                XomashyoHarakat.objects.create(
                    xomashyo=xomashyo,
                    harakat_turi='kirim',
                    miqdori=miqdor_decimal,
                    narxi=narx_decimal,
                    izoh=izoh or f"{xomashyo.nomi} sotib olindi",
                    yetkazib_beruvchi=yetkazib_beruvchi,
                    foydalanuvchi=request.user if request.user.is_authenticated else None
                )
                
                messages.success(
                    request, 
                    f"✅ {xomashyo.nomi} ({miqdor_decimal} {xomashyo.get_olchov_birligi_display()}) "
                    f"muvaffaqiyatli sotib olindi! Chiqim avtomatik yaratildi."
                )
                
            elif chiqim_turi == 'boshqa':
                # Oddiy chiqim
                name = request.POST.get('name')
                price = request.POST.get('price')
                category_id = request.POST.get('category')
                
                # Validatsiya
                if not name:
                    messages.error(request, 'Chiqim nomini kiriting!')
                    return redirect('crm:chiqimlar')
                
                if not price or int(price) <= 0:
                    messages.error(request, 'Narxni to\'g\'ri kiriting!')
                    return redirect('crm:chiqimlar')
                
                # Kategoriya
                category = None
                if category_id:
                    category = ChiqimTuri.objects.get(id=category_id)
                
                # Chiqim yaratish
                Chiqim.objects.create(
                    name=name,
                    price=int(price),
                    category=category
                )
                
                messages.success(request, f"✅ {name} chiqimi muvaffaqiyatli qo'shildi!")
            
            else:
                messages.error(request, 'Chiqim turini tanlang!')
                
        except Decimal.InvalidOperation:
            messages.error(request, 'Son formatida xatolik!')
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
    return redirect('xomashyo:chiqimlar')


def chiqim_ochirish(request, pk):
    """Chiqimni o'chirish"""
    if request.method == 'POST':
        try:
            chiqim = get_object_or_404(Chiqim, id=pk)
            chiqim_nomi = chiqim.name
            chiqim.delete()
            messages.success(request, f"✅ {chiqim_nomi} o'chirildi!")
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
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
    
    # Har bir xomashyo uchun hisob
    xomashyo_list = []
    jami_kirim = 0
    jami_chiqim = 0
    jami_qoldiq = 0
    
    for xomashyo in xomashyolar:
        # Harakatlar query
        harakatlar_query = XomashyoHarakat.objects.filter(
            Q(xomashyo=xomashyo) | Q(xomashyo_variant__xomashyo=xomashyo)
        )
        
        # Sana filtri
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
    
    # Eng ko'p ishlatiladigan
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