from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, DetailView, FormView, View
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, ExpressionWrapper,DecimalField
from django.http import JsonResponse, HttpResponseForbidden
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from crm import models as m
from crm.models import Chiqim, ChiqimTuri
from xomashyo.models import Xomashyo, XomashyoHarakat, YetkazibBeruvchi,Teri


# ==================== PERMISSION HELPERS ====================

def is_admin(user):
    """Admin yoki staff ekanligini tekshirish"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def is_authenticated_user(user):
    """Faqat login bo'lganligini tekshirish"""
    return user.is_authenticated


class AdminRequiredMixin(UserPassesTestMixin):
    """Admin huquqini talab qiladigan mixin"""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        )
    
    def handle_no_permission(self):
        messages.error(self.request, '❌ Sizda bu sahifaga kirish huquqi yo\'q!')
        return redirect('account_login')  # yoki 'main:home'


class StaffRequiredMixin(UserPassesTestMixin):
    """Staff huquqini talab qiladigan mixin"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, '❌ Sizda bu amalni bajarish huquqi yo\'q!')
        return redirect('account_login')


# ==================== HOME ====================

class HomeView(LoginRequiredMixin, ListView):
    model = m.Ishchi
    template_name = "index.html"
    login_url = 'account_login'
    
    def handle_no_permission(self):
        messages.error(self.request, '❌ Iltimos avval tizimga kiring!')
        return super().handle_no_permission()
     
    def get_context_data(self, **kwargs):
        context =  super().get_context_data(**kwargs)
        
        now = timezone.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_sales = m.Sotuv.objects.filter(sana__gte=current_month_start)
        monthly_outlays = m.Chiqim.objects.filter(created__gte=current_month_start)
        
        monthly_sales = monthly_sales.annotate(
            profit=ExpressionWrapper(
                F('mahsulot__avg_profit') * F('miqdor'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        total_profit = monthly_sales.aggregate(total=Sum('profit'))['total'] or 0
        context['salary_sum'] = m.Ish.objects.aggregate(umumiy=Sum('narxi'))['umumiy'] or 0
        context['monthly_outlays'] = monthly_outlays.aggregate(total=Sum('price'))['total'] or 0
        context['monthly_sales'] = monthly_sales
        context['total_profit'] = total_profit
        context['products'] = m.Product.objects.all().aggregate(total_son=Sum('soni'))['total_son']
        context['employees'] = m.Ishchi.objects.filter(is_active=True).count()
        
        return context


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def oylik_yopish(request, pk):
    """
    Ishchi uchun joriy oylikni yopadi va oylik ma'lumotlarini Oyliklar modeliga saqlaydi.
    FAQAT ADMIN
    """
    ishchi = get_object_or_404(m.Ishchi, pk=pk)

    if request.method == "POST":
        if not ishchi.is_oylik_open:
            messages.warning(request, 'Oylik allaqachon yopilgan!')
            return redirect('main:employee_detail', pk=pk)

        umumiy_oylik = sum(ish.narxi for ish in m.Ish.objects.filter(ishchi=ishchi))
        ishlari = m.Ish.objects.filter(ishchi=ishchi)

        oylik_yozuv = m.Oyliklar.objects.create(
            ishchi=ishchi,
            oylik=umumiy_oylik,
            yopilgan=True
        )

        for ish in ishlari:
            m.EskiIsh.objects.create(
                ishchi=ish.ishchi,
                mahsulot=ish.mahsulot.nomi,
                soni=ish.soni,
                sana=ish.sana,
                narxi=ish.narxi,
                ishchi_oylik=oylik_yozuv
            )
            
        ishchi.oldingi_oylik = umumiy_oylik
        ishchi.is_oylik_open = False
        ishchi.save()

        m.Ish.objects.filter(ishchi=ishchi).delete()
        messages.success(request, f'✅ {ishchi.ism} uchun oylik yopildi!')

    return redirect('main:employee_detail', pk=pk)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def yangi_oy_boshlash(request, pk):
    """
    Yangi oylikni yaratadi va uni Ishchi modeliga bog'laydi.
    FAQAT ADMIN
    """
    ishchi = get_object_or_404(m.Ishchi, pk=pk)

    if request.method == "POST":
        if ishchi.is_oylik_open:
            messages.warning(request, 'Oylik allaqachon ochiq!')
            return redirect('main:employee_detail', pk=pk)

        ishchi.is_oylik_open = True
        ishchi.save()
        messages.success(request, f'✅ {ishchi.ism} uchun yangi oy boshlandi!')

    return redirect('main:employee_detail', pk=pk)


# ==================== EMPLOYEES ====================

class EmployeeView(LoginRequiredMixin, ListView):
    """Ishchilar ro'yxati - Barcha login qilgan foydalanuvchilar"""
    model = m.Ishchi
    template_name = "employees_list.html"
    context_object_name = 'ishchilar'
    login_url = 'account_login'
    
    def get_queryset(self):
        return m.Ishchi.objects.all().order_by('ism', 'familiya')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ishchi_turlari'] = m.IshchiCategory.objects.all()
        # Admin ekanligini ham yuboramiz
        context['is_admin'] = is_admin(self.request.user)
        return context


class EmployeeCreateView(AdminRequiredMixin, CreateView):
    """Yangi ishchi qo'shish - FAQAT ADMIN"""
    model = m.Ishchi
    template_name = 'employees.html'
    fields = ['ism', 'familiya', 'maosh', 'telefon', 'turi', 'is_oylik_open', 'yangi_oylik']
    success_url = reverse_lazy("main:employee")
    
    def form_valid(self, form):
        messages.success(self.request, '✅ Yangi ishchi qo\'shildi!')
        return super().form_valid(form)


class EmployeeDeleteView(AdminRequiredMixin, DeleteView):
    """Ishchini o'chirish - FAQAT ADMIN"""
    model = m.Ishchi
    success_url = reverse_lazy("main:employee")
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        ishchi_nomi = f"{self.object.ism} {self.object.familiya}"
        self.object.delete()
        
        # AJAX
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "ok", "message": f"{ishchi_nomi} o'chirildi"})
        
        messages.success(request, f'✅ {ishchi_nomi} o\'chirildi!')
        return redirect(self.success_url)


class EmployeeUpdateView(AdminRequiredMixin, UpdateView):
    """Ishchi ma'lumotlarini tahrirlash - FAQAT ADMIN"""
    model = m.Ishchi
    fields = ['ism', 'familiya', 'maosh', 'telefon', 'turi', 'is_oylik_open']
    success_url = reverse_lazy("main:employee")
    template_name = "employees_list.html"
    
    def form_valid(self, form):
        messages.success(self.request, '✅ Ma\'lumotlar yangilandi!')
        return super().form_valid(form)


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    """Ishchi tafsilotlari - Barcha login qilgan foydalanuvchilar"""
    model = m.Ishchi
    template_name = "employee_detail.html"
    context_object_name = "ishchi"
    login_url = 'account_login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ishchi = self.object
        context['oy_stat'] = ishchi.oy_mahsulotlar()
        context['ish_soni'] = m.Ish.objects.filter(ishchi=ishchi).aggregate(total=Sum('soni'))
        context['is_admin'] = is_admin(self.request.user)
        return context

# ==================== PRODUCTS ====================

class ProductsView(LoginRequiredMixin, ListView):
    """Mahsulotlar ro'yxati - Barcha login qilgan foydalanuvchilar"""
    model = m.Product
    template_name = "product_list.html"
    context_object_name = "products"
    login_url = 'account_login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = is_admin(self.request.user)
        return context



class IshQoshishView(AdminRequiredMixin, View):
    """Ishchiga ish biriktirish - FAQAT ADMIN"""
    template_name = 'ish_qoshish.html'

    def get(self, request, *args, **kwargs):
        context = {
            'ishchilar': m.Ishchi.objects.filter(is_oylik_open=True).select_related('turi'),
            'mahsulotlar': m.Product.objects.all(),
            'terilar': Xomashyo.objects.filter(
                category__name__iexact='teri',
                holati='active',
                miqdori__gt=0
            ).order_by('nomi'),
            'astarlar': Xomashyo.objects.filter(
                category__name__iexact='astar',
                holati='active',
                miqdori__gt=0
            ).order_by('nomi')
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        ishchi_id = request.POST.get('ishchi')
        mahsulot_id = request.POST.get('mahsulot')
        soni = request.POST.get('soni')
        
        try:
            with transaction.atomic():
                # 1. Asosiy obyektlarni olish
                ishchi = m.Ishchi.objects.select_related('turi').get(id=ishchi_id)
                mahsulot = m.Product.objects.get(id=mahsulot_id)
                soni_int = int(soni)
                
                if soni_int < 1:
                    raise ValueError("❌ Son 1 dan katta bo'lishi kerak!")
                
                # 2. Ishchi turini aniqlash
                ishchi_turi = ishchi.turi.nomi.lower() if ishchi.turi else None
                
                # 3. KROY UCHUN MAXSUS LOGIKA
                if ishchi_turi == 'kroy':
                    teri_id = request.POST.get('teri')
                    teri_miqdori_str = m.Product.objects.get(id=mahsulot_id).teri_sarfi
                    astar_id = request.POST.get('astar')  # ixtiyoriy
                    astar_miqdori_str = m.Product.objects.get(id=mahsulot_id).astar_sarfi  # ixtiyoriy
                    
                    # TERI MAJBURIY
                    if not teri_id :
                        raise ValueError("❌ Kroy uchun teri va teri miqdorini kiriting!")
                    
                    teri = Xomashyo.objects.get(
                        id=teri_id,
                        category__name__iexact='teri',
                        holati='active'
                    )
                    teri_miqdori = Decimal(teri_miqdori_str)
                    
                    if teri_miqdori <= 0:
                        raise ValueError("❌ Teri miqdori 0 dan katta bo'lishi kerak!")
                    
                    # Teri yetarliligini tekshirish
                    if teri.miqdori < teri_miqdori:
                        raise ValueError(
                            f"❌ Omborda yetarli {teri.nomi} yo'q! "
                            f"Kerak: {teri_miqdori} {teri.get_olchov_birligi_display()}, "
                            f"Mavjud: {teri.miqdori} {teri.get_olchov_birligi_display()}"
                        )
                    
                    # ASTAR (ixtiyoriy)
                    astar = None
                    astar_miqdori = Decimal('0')
                    if astar_id and astar_miqdori_str:
                        try:
                            astar = Xomashyo.objects.get(
                                id=astar_id,
                                category__name__iexact='astar',
                                holati='active'
                            )
                            astar_miqdori = Decimal(astar_miqdori_str)
                            
                            if astar_miqdori > 0:
                                # Astar yetarliligini tekshirish
                                if astar.miqdori < astar_miqdori:
                                    raise ValueError(
                                        f"❌ Omborda yetarli {astar.nomi} yo'q! "
                                        f"Kerak: {astar_miqdori} {astar.get_olchov_birligi_display()}, "
                                        f"Mavjud: {astar.miqdori} {astar.get_olchov_birligi_display()}"
                                    )
                        except Xomashyo.DoesNotExist:
                            raise ValueError("❌ Tanlangan astar topilmadi!")
                    
                    # 4. ISH YARATISH
                    ish = m.Ish.objects.create(
                        ishchi=ishchi,
                        mahsulot=mahsulot,
                        soni=soni_int
                    )
                    
                    # 5. TERI CHIQIMI (XomashyoHarakat)
                    XomashyoHarakat.objects.create(
                        xomashyo=teri,
                        harakat_turi='chiqim',
                        miqdori=teri_miqdori*soni_int,
                        narxi=teri.narxi * teri_miqdori,
                        izoh=f"Kroy ishiga sarflandi: {mahsulot.nomi} x{soni_int} ({ishchi.ism})",
                        foydalanuvchi=request.user
                    )
                    
                    # 6. ASTAR CHIQIMI (agar tanlangan bo'lsa)
                    if astar and astar_miqdori > 0:
                        XomashyoHarakat.objects.create(
                            xomashyo=astar,
                            harakat_turi='chiqim',
                            miqdori=astar_miqdori*soni_int,
                            narxi=astar.narxi * astar_miqdori,
                            izoh=f"Kroy ishiga sarflandi: {mahsulot.nomi} x{soni_int} ({ishchi.ism})",
                            foydalanuvchi=request.user
                        )
                    
                    # Muvaffaqiyatli xabar
                    success_msg = (
                        f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} qo'shildi!\n"
                        f" Teri: {teri.nomi} ({teri_miqdori*soni_int} {teri.get_olchov_birligi_display()})"
                    )
                    if astar and astar_miqdori > 0:
                        success_msg += f"\n🔶 Astar: {astar.nomi} ({astar_miqdori} {astar.get_olchov_birligi_display()})"
                    
                    messages.success(request, success_msg)
                
                else:
                    # 4. ODDIY ISH (kroy emas)
                    ish = m.Ish.objects.create(
                        ishchi=ishchi,
                        mahsulot=mahsulot,
                        soni=soni_int
                    )
                    
                    messages.success(
                        request,
                        f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} qo'shildi!"
                    )
                
        except m.Ishchi.DoesNotExist:
            messages.error(request, "❌ Ishchi topilmadi!")
        except m.Product.DoesNotExist:
            messages.error(request, "❌ Mahsulot topilmadi!")
        except Xomashyo.DoesNotExist:
            messages.error(request, "❌ Xomashyo topilmadi!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
        
        return redirect('main:ish_qoshish')
    
# ==================== SOTUVLAR ====================

class SotuvListView(LoginRequiredMixin, ListView):
    """Sotuvlar ro'yxati - Barcha login qilgan foydalanuvchilar"""
    model = m.Sotuv
    template_name = 'sotuv_list.html'
    context_object_name = 'sotuvlar'
    ordering = ['-sana']
    paginate_by = 50
    login_url = 'account_login'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Qidiruv
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(xaridor__ism__icontains=search) |
                Q(mahsulot__nomi__icontains=search) |
                Q(xaridor__telefon__icontains=search)
            )
        
        # Sana filtri
        date_filter = self.request.GET.get('date')
        if date_filter == 'bugun':
            queryset = queryset.filter(sana__date=date.today())
        elif date_filter == 'hafta':
            week_ago = date.today() - timedelta(days=7)
            queryset = queryset.filter(sana__date__gte=week_ago)
        elif date_filter == 'oy':
            queryset = queryset.filter(
                sana__year=date.today().year,
                sana__month=date.today().month
            )
        
        return queryset.select_related('xaridor', 'mahsulot')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        # Statistika
        context['bugungi_sotuv'] = m.Sotuv.objects.filter(
            sana__date=today
        ).aggregate(Sum('umumiy_summa'))['umumiy_summa__sum'] or 0
        
        context['bugungi_soni'] = m.Sotuv.objects.filter(
            sana__date=today
        ).count()
        
        context['oylik_sotuv'] = m.Sotuv.objects.filter(
            sana__year=today.year,
            sana__month=today.month
        ).aggregate(Sum('umumiy_summa'))['umumiy_summa__sum'] or 0
        
        context['jami_sotuv'] = m.Sotuv.objects.aggregate(
            Sum('umumiy_summa')
        )['umumiy_summa__sum'] or 0
        
        # Form uchun ma'lumotlar
        context['xaridorlar'] = m.Xaridor.objects.all().order_by('-created_at')[:20]
        context['mahsulotlar'] = m.Product.objects.filter(soni__gt=0).order_by('nomi')
        context['is_admin'] = is_admin(self.request.user)
        
        return context


@login_required(login_url='login')
def sotuv_qoshish(request):
    """Yangi sotuv qo'shish - Barcha login qilgan foydalanuvchilar"""
    if request.method == 'POST':
        try:
            xaridor_turi = request.POST.get('xaridor_turi')
            mahsulot_id = request.POST.get('mahsulot')
            miqdor = request.POST.get('miqdor')
            
            # Validatsiya
            if not mahsulot_id:
                messages.error(request, 'Mahsulotni tanlang!')
                return redirect('main:sotuvlar')
            
            if not miqdor or int(miqdor) <= 0:
                messages.error(request, 'Miqdorni to\'g\'ri kiriting!')
                return redirect('main:sotuvlar')
            
            mahsulot = get_object_or_404(m.Product, id=mahsulot_id)
            miqdor_int = int(miqdor)
            
            # Mahsulot yetarlimi?
            if mahsulot.soni < miqdor_int:
                messages.error(
                    request, 
                    f'Omborda yetarli {mahsulot.nomi} yo\'q! Mavjud: {mahsulot.soni} ta'
                )
                return redirect('main:sotuvlar')
            
            # Xaridor
            if xaridor_turi == 'yangi':
                xaridor_ism = request.POST.get('xaridor_ism')
                xaridor_telefon = request.POST.get('xaridor_telefon')
                xaridor_manzil = request.POST.get('xaridor_manzil')
                
                if not xaridor_ism:
                    messages.error(request, 'Xaridor ismini kiriting!')
                    return redirect('main:sotuvlar')
                
                xaridor = m.Xaridor.objects.create(
                    ism=xaridor_ism,
                    telefon=xaridor_telefon,
                    manzil=xaridor_manzil
                )
            else:
                xaridor_id = request.POST.get('xaridor')
                if not xaridor_id:
                    messages.error(request, 'Xaridorni tanlang!')
                    return redirect('main:sotuvlar')
                xaridor = get_object_or_404(m.Xaridor, id=xaridor_id)
            
            # Sotuv yaratish
            sotuv = m.Sotuv.objects.create(
                xaridor=xaridor,
                mahsulot=mahsulot,
                miqdor=miqdor_int
            )
            
            messages.success(
                request,
                f"✅ {mahsulot.nomi} ({miqdor_int} ta) {xaridor.ism}ga sotildi! "
                f"Summa: {sotuv.umumiy_summa:,.0f} so'm"
            )
            
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
    return redirect('main:sotuvlar')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def sotuv_ochirish(request, pk):
    """Sotuvni o'chirish - FAQAT ADMIN"""
    if request.method == 'POST':
        try:
            sotuv = get_object_or_404(m.Sotuv, id=pk)
            
            # Mahsulot sonini qaytarish
            mahsulot = sotuv.mahsulot
            mahsulot.soni += sotuv.miqdor
            mahsulot.save()
            
            sotuv_info = f"{sotuv.xaridor.ism} - {sotuv.mahsulot.nomi}"
            sotuv.delete()
            
            messages.success(request, f"✅ Sotuv o'chirildi: {sotuv_info}")
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
    return redirect('main:sotuvlar')


# ==================== KIRIMLAR ====================

class KirimListView(LoginRequiredMixin, ListView):
    """Kirimlar ro'yxati - Barcha login qilgan foydalanuvchilar"""
    model = m.Kirim
    template_name = 'kirim_list.html'
    context_object_name = 'kirimlar'
    ordering = ['-sana']
    paginate_by = 50
    login_url = 'account_login'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(xaridor__ism__icontains=search) |
                Q(mahsulot__nomi__icontains=search)
            )
        
        date_filter = self.request.GET.get('date')
        if date_filter == 'bugun':
            queryset = queryset.filter(sana__date=date.today())
        elif date_filter == 'hafta':
            week_ago = date.today() - timedelta(days=7)
            queryset = queryset.filter(sana__date__gte=week_ago)
        elif date_filter == 'oy':
            queryset = queryset.filter(
                sana__year=date.today().year,
                sana__month=date.today().month
            )
        
        return queryset.select_related('xaridor', 'mahsulot', 'sotuv')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        context['bugungi_kirim'] = m.Kirim.objects.filter(
            sana__date=today
        ).aggregate(Sum('summa'))['summa__sum'] or 0
        
        context['oylik_kirim'] = m.Kirim.objects.filter(
            sana__year=today.year,
            sana__month=today.month
        ).aggregate(Sum('summa'))['summa__sum'] or 0
        
        context['jami_kirim'] = m.Kirim.objects.aggregate(
            Sum('summa')
        )['summa__sum'] or 0
        
        context['top_mahsulotlar'] = m.Kirim.objects.values(
            'mahsulot__nomi'
        ).annotate(
            jami=Sum('summa'),
            soni=Count('id')
        ).order_by('-jami')[:5]
        
        return context


# ==================== XARIDORLAR ====================

class XaridorListView(LoginRequiredMixin, ListView):
    """Xaridorlar ro'yxati - Barcha login qilgan foydalanuvchilar"""
    model = m.Xaridor
    template_name = 'xaridor_list.html'
    context_object_name = 'xaridorlar'
    ordering = ['-created_at']
    paginate_by = 50
    login_url = 'account_login'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(ism__icontains=search) |
                Q(telefon__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        xaridorlar = context['xaridorlar']
        for xaridor in xaridorlar:
            xaridor.jami_xarid = xaridor.sales.aggregate(
                Sum('umumiy_summa')
            )['umumiy_summa__sum'] or 0
            xaridor.xaridlar_soni = xaridor.sales.count()
        
        context['jami_xaridorlar'] = m.Xaridor.objects.count()
        context['is_admin'] = is_admin(self.request.user)
        
        return context


class XaridorDetailView(LoginRequiredMixin, DetailView):
    """Xaridor tafsilotlari - Barcha login qilgan foydalanuvchilar"""
    model = m.Xaridor
    template_name = 'xaridor_detail.html'
    context_object_name = 'xaridor'
    login_url = 'account_login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        xaridor = self.object
        
        context['sotuvlar'] = xaridor.sales.select_related(
            'mahsulot'
        ).order_by('-sana')
        
        context['jami_xarid'] = xaridor.sales.aggregate(
            Sum('umumiy_summa')
        )['umumiy_summa__sum'] or 0
        
        context['xaridlar_soni'] = xaridor.sales.count()
        
        context['top_mahsulotlar'] = xaridor.sales.values(
            'mahsulot__nomi'
        ).annotate(
            jami_miqdor=Sum('miqdor'),
            jami_summa=Sum('umumiy_summa')
        ).order_by('-jami_summa')[:5]
        
        return context


@login_required(login_url='login')
def xaridor_qoshish(request):
    """Yangi xaridor qo'shish - Barcha login qilgan foydalanuvchilar"""
    if request.method == 'POST':
        try:
            ism = request.POST.get('ism')
            telefon = request.POST.get('telefon')
            manzil = request.POST.get('manzil')
            izoh = request.POST.get('izoh')
            
            if not ism:
                messages.error(request, 'Ism kiritilmagan!')
                return redirect('main:xaridorlar')
            
            xaridor = m.Xaridor.objects.create(
                ism=ism,
                telefon=telefon,
                manzil=manzil,
                izoh=izoh
            )
            
            messages.success(request, f"✅ {xaridor.ism} xaridor qo'shildi!")
            
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
    return redirect('main:xaridorlar')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def xaridor_tahrirlash(request, pk):
    """Xaridorni tahrirlash - FAQAT ADMIN"""
    xaridor = get_object_or_404(m.Xaridor, id=pk)
    
    if request.method == 'POST':
        try:
            xaridor.ism = request.POST.get('ism', xaridor.ism)
            xaridor.telefon = request.POST.get('telefon', xaridor.telefon)
            xaridor.manzil = request.POST.get('manzil', xaridor.manzil)
            xaridor.izoh = request.POST.get('izoh', xaridor.izoh)
            xaridor.save()
            
            messages.success(request, f"✅ {xaridor.ism} ma'lumotlari yangilandi!")
            
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
        
        return redirect('main:xaridor_detail', pk=pk)
    
    return redirect('main:xaridorlar')


# ==================== CHIQIMLAR (XOMASHYO APP) ====================

class ChiqimListView(AdminRequiredMixin, ListView):
    """Chiqimlar ro'yxati - FAQAT ADMIN"""
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
            created__month=today.month
        ).aggregate(Sum('price'))['price__sum'] or 0
        
        context['jami_chiqim'] = Chiqim.objects.aggregate(
            Sum('price')
        )['price__sum'] or 0
        
        context['xomashyolar'] = Xomashyo.objects.filter(
            holati='active'
        ).order_by('nomi')
        
        context['chiqim_turlari'] = ChiqimTuri.objects.all()
        context['yetkazib_beruvchilar'] = YetkazibBeruvchi.objects.all()
        
        return context


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def chiqim_qoshish(request):
    """Yangi chiqim qo'shish - FAQAT ADMIN"""
    if request.method == 'POST':
        chiqim_turi = request.POST.get('chiqim_turi')
        
        try:
            if chiqim_turi == 'xomashyo':
                xomashyo_id = request.POST.get('xomashyo')
                miqdor = request.POST.get('miqdor')
                narx = request.POST.get('xomashyo_narx')
                yetkazib_beruvchi_id = request.POST.get('yetkazib_beruvchi')
                izoh = request.POST.get('izoh', '')
                
                if not xomashyo_id:
                    messages.error(request, 'Xomashyoni tanlang!')
                    return redirect('xomashyo:chiqimlar')
                
                if not miqdor or Decimal(miqdor) <= 0:
                    messages.error(request, 'Miqdorni to\'g\'ri kiriting!')
                    return redirect('xomashyo:chiqimlar')
                
                xomashyo = get_object_or_404(Xomashyo, id=xomashyo_id)
                miqdor_decimal = Decimal(miqdor)
                
                if narx:
                    narx_decimal = Decimal(narx)
                else:
                    narx_decimal = xomashyo.narxi * miqdor_decimal
                
                yetkazib_beruvchi = None
                if yetkazib_beruvchi_id:
                    yetkazib_beruvchi = YetkazibBeruvchi.objects.get(id=yetkazib_beruvchi_id)
                
                XomashyoHarakat.objects.create(
                    xomashyo=xomashyo,
                    harakat_turi='kirim',
                    miqdori=miqdor_decimal,
                    narxi=narx_decimal,
                    izoh=izoh or f"{xomashyo.nomi} sotib olindi",
                    yetkazib_beruvchi=yetkazib_beruvchi,
                    foydalanuvchi=request.user
                )
                
                messages.success(
                    request, 
                    f"✅ {xomashyo.nomi} ({miqdor_decimal} {xomashyo.get_olchov_birligi_display()}) "
                    f"muvaffaqiyatli sotib olindi!"
                )
                
            elif chiqim_turi == 'boshqa':
                name = request.POST.get('name')
                price = request.POST.get('price')
                category_id = request.POST.get('category')
                
                if not name:
                    messages.error(request, 'Chiqim nomini kiriting!')
                    return redirect('xomashyo:chiqimlar')
                
                if not price or int(price) <= 0:
                    messages.error(request, 'Narxni to\'g\'ri kiriting!')
                    return redirect('xomashyo:chiqimlar')
                
                category = None
                if category_id:
                    category = ChiqimTuri.objects.get(id=category_id)
                
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


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def chiqim_ochirish(request, pk):
    """Chiqimni o'chirish - FAQAT ADMIN"""
    if request.method == 'POST':
        try:
            chiqim = get_object_or_404(Chiqim, id=pk)
            chiqim_nomi = chiqim.name
            chiqim.delete()
            messages.success(request, f"✅ {chiqim_nomi} o'chirildi!")
        except Exception as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
    
    return redirect('xomashyo:chiqimlar')


from rest_framework import generics
from .serializers import ProductSerializer

class ProductCreateView(generics.CreateAPIView):
    queryset = m.Product.objects.all()
    serializer_class = ProductSerializer

