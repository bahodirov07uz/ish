#xomashyo app
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import ListView
from django.urls import reverse_lazy
from django.db.models import Sum
from datetime import date
from decimal import Decimal

from crm.models import Chiqim, ChiqimTuri
from .models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi


class ChiqimListView(ListView):
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