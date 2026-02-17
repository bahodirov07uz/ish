from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, DeleteView, UpdateView, DetailView, View
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, ExpressionWrapper,DecimalField
from django.http import JsonResponse
from datetime import date, timedelta,datetime
from decimal import Decimal,InvalidOperation
from django.utils import timezone
from django.db import transaction
import traceback
import json
from crm import models as m
from crm.models import Chiqim, ChiqimTuri,IshXomashyo
from xomashyo.models import Xomashyo, YetkazibBeruvchi,XomashyoCategory,XomashyoVariant
import logging

logger = logging.getLogger(__name__)


def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def is_authenticated_user(user):
    return user.is_authenticated


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_staff or self.request.user.is_superuser
        )
    
    def handle_no_permission(self):
        messages.error(self.request, '❌ Sizda bu sahifaga kirish huquqi yo\'q!')
        return redirect('account_login')  


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff
    
    def handle_no_permission(self):
        messages.error(self.request, '❌ Sizda bu amalni bajarish huquqi yo\'q!')
        return redirect('account_login')



class HomeView(LoginRequiredMixin, ListView):
    model = m.Ishchi
    template_name = "index.html"
    login_url = 'account_login'

    def handle_no_permission(self):
        messages.error(self.request, '❌ Iltimos avval tizimga kiring!')
        return super().handle_no_permission()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        monthly_sales = m.Sotuv.objects.filter(sana__gte=current_month_start)
        monthly_outlays = m.Chiqim.objects.filter(created__gte=current_month_start)

        # ✅ Profit: Sotuv -> items -> variant(avg_profit) * miqdor
        total_profit = monthly_sales.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F('items__variant__product__avg_profit') * F('items__miqdor'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
        )['total'] or 0

        context['salary_sum'] = m.Ish.objects.aggregate(umumiy=Sum('narxi'))['umumiy'] or 0
        context['monthly_outlays'] = monthly_outlays.aggregate(total=Sum('price'))['total'] or 0
        context['monthly_sales'] = monthly_sales
        context['total_profit'] = total_profit
        context['products'] = m.ProductVariant.objects.all().aggregate(total_son=Sum('stock'))['total_son'] or 0
        context['employees'] = m.Ishchi.objects.filter(is_active=True).count()

        return context

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def oylik_yopish(request, pk):

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

        m.Ish.objects.update(
            status='yopilgan'
        )
        messages.success(request, f'✅ {ishchi.ism} uchun oylik yopildi!')

    return redirect('main:employee_detail', pk=pk)


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')
def yangi_oy_boshlash(request, pk):

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
    model = m.Ishchi
    template_name = "employees_list.html"
    context_object_name = 'ishchilar'
    login_url = 'account_login'
    
    def get_queryset(self):
        return m.Ishchi.objects.all().order_by('ism', 'familiya')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ishchi_turlari'] = m.IshchiCategory.objects.all()
        context['is_admin'] = is_admin(self.request.user)
        return context


class EmployeeCreateView(AdminRequiredMixin, CreateView):
    model = m.Ishchi
    template_name = 'employees.html'
    fields = ['ism', 'familiya', 'maosh', 'telefon', 'turi', 'is_oylik_open', 'yangi_oylik']
    success_url = reverse_lazy("main:employee")
    
    def form_valid(self, form):
        messages.success(self.request, '✅ Yangi ishchi qo\'shildi!')
        return super().form_valid(form)


class EmployeeDeleteView(AdminRequiredMixin, DeleteView):
    model = m.Ishchi
    success_url = reverse_lazy("main:employee")
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        ishchi_nomi = f"{self.object.ism} {self.object.familiya}"
        self.object.delete()
        
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
        test  = ishchi.umumiy_oylik()
        context['oy_stat'] = ishchi.oy_mahsulotlar()
        context['ish_soni'] = m.Ish.objects.filter(ishchi=ishchi, status='yangi').aggregate(total=Sum('soni'))
        context['ishlar'] = m.Ish.objects.filter(ishchi=ishchi, status='yangi')
        test = ishchi.umumiy_oylik()
        # Avanslarni qo'shamiz
        avanslar = m.Avans.objects.filter(ishchi=ishchi).order_by('-created')

       
        total_avans = avanslar.aggregate(Sum('amount'))['amount__sum'] or 0

        # Context'ga uzatish
        context['avanslar'] = avanslar
        context['beriladi'] = test - total_avans
        context['total_avans'] = total_avans        
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


class IshQoshishView(AdminRequiredMixin,View):
    """Ishchiga ish biriktirish - TeriSarfi bilan yangilangan versiya"""
    template_name = 'ish_qoshish.html'

    def get(self, request, *args, **kwargs):
        """GET so'rov - forma ko'rsatish"""

        terilar = Xomashyo.objects.filter(
            category__name__iexact='teri',
            category__turi='real',
            holati='active',
            miqdori__gt=0
        ).select_related('category').prefetch_related('variantlar').order_by('nomi')

        astarlar = Xomashyo.objects.filter(
            category__name__iexact='astar',
            category__turi='real',
            holati='active',
            miqdori__gt=0
        ).select_related('category').prefetch_related('variantlar').order_by('nomi')

        padojlar = Xomashyo.objects.filter(
            category__name__iexact='padoj',
            category__turi='real',
            holati='active',
            miqdori__gt=0
        ).select_related('category').prefetch_related('variantlar').order_by('nomi')

        context = {
            'ishchilar': m.Ishchi.objects.filter(
                is_oylik_open=True
            ).select_related('turi').order_by('ism'),
            'mahsulotlar': m.Product.objects.all().order_by('nomi'),
            'terilar': terilar,
            'astarlar': astarlar,
            'padojlar': padojlar,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        logger.info("post")
        """POST so'rov - ish yaratish"""
        ishchi_id = request.POST.get('ishchi')
        mahsulot_id = request.POST.get('mahsulot')
        soni = request.POST.get('soni')
        ish_sanasi = request.POST.get('ish_sanasi')
        mustaqil_ish = request.POST.get('mustaqil_ish') == 'on'

        try:
            with transaction.atomic():
                ishchi = m.Ishchi.objects.select_related('turi').get(id=ishchi_id)
                mahsulot = m.Product.objects.get(id=mahsulot_id)
                soni_int = int(soni)

                if soni_int < 1:
                    raise ValueError("❌ Son 1 dan katta bo'lishi kerak!")

                # Ish sanasini tekshirish
                if ish_sanasi:
                    try:
                        ish_sana_obj = datetime.strptime(ish_sanasi, '%Y-%m-%d').date()
                    except ValueError:
                        raise ValueError("❌ Sana formati noto'g'ri!")
                else:
                    ish_sana_obj = datetime.now().date()

                ishchi_turi = ishchi.turi.nomi.lower() if ishchi.turi else None
                if not ishchi_turi:
                    raise ValueError("❌ Ishchi turi ko'rsatilmagan!")

                # ============================================================
                # ZAKATOVKA
                # ============================================================
                if ishchi_turi == 'zakatovka':
                    kroy_xomashyo_id = request.POST.get('kroy_xomashyo')

                    # Mustaqil ish - kroy xomashyosiz
                    if mustaqil_ish:
                        ish = m.Ish.objects.create(
                            ishchi=ishchi,
                            mahsulot=mahsulot,
                            soni=soni_int,
                            status='yangi',
                            sana=ish_sana_obj
                        )

                        # Faqat zakatovka jarayon xomashyo yaratish
                        zakatovka_xomashyo = self._get_or_create_jarayon_xomashyo(
                            mahsulot=mahsulot,
                            category_name='zakatovka',
                            miqdor=Decimal(soni_int)
                        )

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=zakatovka_xomashyo,
                            miqdor=Decimal(soni_int)
                        )

                        messages.warning(
                            request,
                            f"⚠️ MUSTAQIL ISH: {ishchi.ism}ga {mahsulot.nomi} x{soni_int} (Zakatovka) "
                            f"kroy xomashyosiz qo'shildi!\n"
                            f"📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"
                        )

                    # Standart ish - kroy xomashyo bilan
                    else:
                        if not kroy_xomashyo_id:
                            raise ValueError(
                                "❌ Kroy xomashyosi tanlanmagan! "
                                "'Mustaqil ish' belgisini yoqing yoki kroy xomashyosini tanlang."
                            )

                        kroy_xomashyo = Xomashyo.objects.get(
                            id=kroy_xomashyo_id,
                            category__name__iexact='kroy',
                            category__turi='process',
                            holati='active'
                        )

                        if kroy_xomashyo.miqdori < soni_int:
                            raise ValueError(
                                f"❌ Yetarli kroy xomashyo yo'q! "
                                f"Kerak: {soni_int}, Mavjud: {kroy_xomashyo.miqdori}"
                            )

                        ish = m.Ish.objects.create(
                            ishchi=ishchi,
                            mahsulot=mahsulot,
                            soni=soni_int,
                            status='yangi',
                            sana=ish_sana_obj
                        )

                        # Kroy xomashyo chiqimi
                        kroy_xomashyo.miqdori -= Decimal(soni_int)
                        kroy_xomashyo.save(update_fields=['miqdori', 'updated_at'])

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=kroy_xomashyo,
                            miqdor=Decimal(soni_int)
                        )

                        # Zakatovka jarayon xomashyo
                        zakatovka_xomashyo = self._get_or_create_jarayon_xomashyo(
                            mahsulot=mahsulot,
                            category_name='zakatovka',
                            miqdor=Decimal(soni_int)
                        )

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=zakatovka_xomashyo,
                            miqdor=Decimal(soni_int)
                        )

                        messages.success(
                            request,
                            f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} (Zakatovka) qo'shildi!\n"
                            f"🔶 Ishlatildi: {kroy_xomashyo.nomi} (-{soni_int} dona)\n"
                            f"📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"
                        )

                # ============================================================
                # KROY VA REZAK - TeriSarfi bilan
                # ============================================================

                if ishchi_turi in ['kroy', 'rezak']:
                    # Multiple teri sarflarini olish
                    teri_xomashyo_ids = request.POST.getlist('teri_xomashyo[]')
                    teri_variant_ids = request.POST.getlist('teri_variant[]')
                    teri_sarfi_customs = request.POST.getlist('teri_sarfi_custom[]')

                    # ============================================================
                    # KRITIK FIX: Bo'sh stringlarni filtrlash
                    # ============================================================
                    # Bo'sh ID'larni olib tashlash
                    teri_xomashyo_ids = [x.strip() for x in teri_xomashyo_ids if x and x.strip()]
                    
                    # Bo'sh variant ID'larni None ga aylantirish (muhim!)
                    teri_variant_ids = [
                        x.strip() if x and x.strip() else None 
                        for x in teri_variant_ids
                    ]
                    
                    # Astar (yagona)
                    astar_xomashyo_id = request.POST.get('astar_xomashyo', '').strip() or None
                    astar_variant_id = request.POST.get('astar_variant', '').strip() or None
                    astar_sarfi_custom = request.POST.get('astar_sarfi_custom', '').strip() or None

                    # Validatsiya
                    if not teri_xomashyo_ids:
                        raise ValueError(f"❌ {ishchi_turi.title()} uchun kamida bitta teri tanlanishi kerak!")

                    # Teri sarflarini tayyorlash
                    teri_sarflar = []
                    jami_teri_sarfi = Decimal('0')

                    for i, teri_id in enumerate(teri_xomashyo_ids):
                        if not teri_id:
                            continue

                        try:
                            teri_xomashyo = Xomashyo.objects.get(
                                id=teri_id,
                                category__name__iexact='teri',
                                holati='active'
                            )
                        except Xomashyo.DoesNotExist:
                            raise ValueError(f"❌ ID {teri_id} bilan teri topilmadi!")

                        # ============================================================
                        # KRITIK: Variant - None tekshiruvi
                        # ============================================================
                        teri_variant = None
                        if i < len(teri_variant_ids) and teri_variant_ids[i] is not None:
                            try:
                                teri_variant = XomashyoVariant.objects.get(
                                    id=teri_variant_ids[i],
                                    xomashyo=teri_xomashyo
                                )
                            except (XomashyoVariant.DoesNotExist, ValueError):
                                logger.warning(f"Variant {teri_variant_ids[i]} topilmadi")
                                teri_variant = None

                        # Sarfni hisoblash
                        teri_sarfi_bitta = mahsulot.teri_sarfi
                        if i < len(teri_sarfi_customs):
                            custom_sarf = teri_sarfi_customs[i]
                            if custom_sarf and custom_sarf.strip():
                                try:
                                    teri_sarfi_bitta = Decimal(custom_sarf)
                                except (ValueError, InvalidOperation):
                                    logger.warning(f"Noto'g'ri sarf: {custom_sarf}")

                        teri_sarfi_jami = teri_sarfi_bitta * soni_int

                        if teri_sarfi_jami <= 0:
                            raise ValueError(f"❌ {teri_xomashyo.nomi} sarfi 0 dan katta bo'lishi kerak!")

                        # Miqdorni tekshirish
                        if teri_variant:
                            if teri_variant.miqdori < teri_sarfi_jami:
                                raise ValueError(
                                    f"❌ {teri_xomashyo.nomi} ({teri_variant.rang}) variantida "
                                    f"yetarli miqdor yo'q! Kerak: {teri_sarfi_jami}, Mavjud: {teri_variant.miqdori}"
                                )
                        else:
                            if teri_xomashyo.miqdori < teri_sarfi_jami:
                                raise ValueError(
                                    f"❌ Omborda yetarli {teri_xomashyo.nomi} yo'q! "
                                    f"Kerak: {teri_sarfi_jami}, Mavjud: {teri_xomashyo.miqdori}"
                                )

                        teri_sarflar.append({
                            'xomashyo': teri_xomashyo,
                            'variant': teri_variant,  # None yoki XomashyoVariant
                            'miqdor': teri_sarfi_jami,
                            'bitta_sarf': teri_sarfi_bitta
                        })

                        jami_teri_sarfi += teri_sarfi_jami

                    # ============================================================
                    # ASTAR (ixtiyoriy)
                    # ============================================================
                    astar_sarfi = Decimal('0')
                    astar_xomashyo = None
                    astar_variant = None

                    if astar_xomashyo_id:
                        try:
                            astar_xomashyo = Xomashyo.objects.get(
                                id=astar_xomashyo_id,
                                category__name__iexact='astar',
                                holati='active'
                            )

                            if astar_sarfi_custom:
                                try:
                                    astar_sarfi = Decimal(astar_sarfi_custom) * soni_int
                                except (ValueError, InvalidOperation):
                                    astar_sarfi = mahsulot.astar_sarfi * soni_int
                            else:
                                astar_sarfi = mahsulot.astar_sarfi * soni_int

                            if astar_sarfi > 0:
                                # KRITIK: Variant None tekshiruvi
                                if astar_variant_id:
                                    try:
                                        astar_variant = XomashyoVariant.objects.get(
                                            id=astar_variant_id,
                                            xomashyo=astar_xomashyo
                                        )
                                        if astar_variant.miqdori < astar_sarfi:
                                            raise ValueError(
                                                f"❌ Astar variantida yetarli miqdor yo'q! "
                                                f"Kerak: {astar_sarfi}, Mavjud: {astar_variant.miqdori}"
                                            )
                                    except (XomashyoVariant.DoesNotExist, ValueError) as e:
                                        if "yetarli" in str(e):
                                            raise
                                        logger.warning(f"Astar variant topilmadi: {astar_variant_id}")
                                        astar_variant = None
                                
                                if not astar_variant:
                                    if astar_xomashyo.miqdori < astar_sarfi:
                                        raise ValueError(
                                            f"❌ Omborda yetarli {astar_xomashyo.nomi} yo'q! "
                                            f"Kerak: {astar_sarfi}, Mavjud: {astar_xomashyo.miqdori}"
                                        )
                        except Xomashyo.DoesNotExist:
                            raise ValueError(f"❌ ID {astar_xomashyo_id} bilan astar topilmadi!")

                    # ============================================================
                    # ISH YARATISH
                    # ============================================================
                    ish = m.Ish.objects.create(
                        ishchi=ishchi,
                        mahsulot=mahsulot,
                        soni=soni_int,
                        status='yangi',
                        sana=ish_sana_obj
                    )
                    logger.info(" creating Ish ")

                    # ============================================================
                    # TERI SARFLARINI YOZISH
                    # ============================================================
                    teri_sarfi_messages = []
                    for sarf in teri_sarflar:
                        # TeriSarfi - KRITIK: timezone.now() ishlatish
                        m.TeriSarfi.objects.create(
                            ish=ish,
                            ishchi=ishchi,
                            xomashyo=sarf['xomashyo'],
                            miqdor=sarf['miqdor'],
                            sana=timezone.now()  # datetime.now() emas!
                        )
                        logger.info(" creating teri terisarfi ")

                        # IshXomashyo
                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=sarf['xomashyo'],
                            miqdor=sarf['miqdor']
                        )
                        logger.info(" creating teri Ishxomashyo ")

                        variant_info = f" ({sarf['variant'].rang})" if sarf['variant'] else ""
                        teri_sarfi_messages.append(
                            f"   • {sarf['xomashyo'].nomi}{variant_info}: "
                            f"{sarf['bitta_sarf']} × {soni_int} = {sarf['miqdor']} Dm"
                        )

                    # ============================================================
                    # ASTAR CHIQIMI
                    # ============================================================
                    if astar_xomashyo and astar_sarfi > 0:
                        if astar_variant:
                            astar_variant.miqdori -= astar_sarfi
                            astar_variant.save(update_fields=['miqdori'])
                        else:
                            astar_xomashyo.miqdori -= astar_sarfi
                            astar_xomashyo.save(update_fields=['miqdori', 'updated_at'])

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=astar_xomashyo,
                            variant=astar_variant,  # None OK
                            miqdor=astar_sarfi
                        )
                        logger.info(" creating Ishxomashyo ")
                    # ============================================================
                    # KROY JARAYON XOMASHYO
                    # ============================================================
                    kroy_xomashyo = self._get_or_create_jarayon_xomashyo(
                        mahsulot=mahsulot,
                        category_name='kroy',
                        miqdor=Decimal(soni_int),
                    )

                    IshXomashyo.objects.create(
                        ish=ish,
                        xomashyo=kroy_xomashyo,
                        variant=None,  # Jarayon - variant yo'q
                        miqdor=Decimal(soni_int)
                    )
                    logger.info("creating ishxomashyo kroy ")

                    # Success message
                    success_msg = (
                        f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} ({ishchi_turi.title()}) qo'shildi!\n\n"
                        f"📊 Teri sarflari ({len(teri_sarflar)} ta):\n"
                    )
                    success_msg += '\n'.join(teri_sarfi_messages)
                    success_msg += f"\n\n🔢 Jami teri sarfi: {jami_teri_sarfi} Dm"

                    if astar_xomashyo and astar_sarfi > 0:
                        success_msg += f"\n🔶 Astar: {astar_xomashyo.nomi} (-{astar_sarfi} Dm)"

                    success_msg += f"\n📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"

                    messages.success(request, success_msg)


                # ============================================================
                # KOSIB
                # ============================================================
                elif ishchi_turi == 'kosib':
                    zakatovka_xomashyo_id = request.POST.get('zakatovka_xomashyo')
                    padoj_xomashyo_id = request.POST.get('padoj_xomashyo')
                    padoj_variant_id = request.POST.get('padoj_variant')
                    mahsulot_variant_id = request.POST.get('mahsulot_variant')
                    variant_rang = request.POST.get('variant_rang', '')
                    variant_razmer = request.POST.get('variant_razmer', '')

                    if not padoj_xomashyo_id:
                        raise ValueError("❌ Kosib uchun padoj tanlanishi kerak!")

                    # Mustaqil ish - zakatovka xomashyosiz
                    if mustaqil_ish:
                        # PADOJ
                        padoj = Xomashyo.objects.get(
                            id=padoj_xomashyo_id,
                            holati='active'
                        )

                        padoj_variant = None
                        if padoj_variant_id:
                            padoj_variant = XomashyoVariant.objects.get(
                                id=padoj_variant_id,
                                xomashyo=padoj
                            )
                            if padoj_variant.miqdori < soni_int:
                                raise ValueError(
                                    f"❌ Padoj variantida yetarli miqdor yo'q! "
                                    f"Kerak: {soni_int}, Mavjud: {padoj_variant.miqdori}"
                                )
                            padoj_variant.miqdori -= Decimal(soni_int)
                            padoj_variant.save(update_fields=['miqdori'])
                        else:
                            if padoj.miqdori < soni_int:
                                raise ValueError(
                                    f"❌ Yetarli {padoj.nomi} yo'q! "
                                    f"Kerak: {soni_int}, Mavjud: {padoj.miqdori}"
                                )
                            padoj.miqdori -= Decimal(soni_int)
                            padoj.save(update_fields=['miqdori', 'updated_at'])

                        # ISH YARATISH
                        ish = m.Ish.objects.create(
                            ishchi=ishchi,
                            mahsulot=mahsulot,
                            soni=soni_int,
                            status='yangi',
                            sana=ish_sana_obj
                        )

                        # PADOJ CHIQIMI
                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=padoj,
                            variant=padoj_variant,
                            miqdor=Decimal(soni_int)
                        )

                        # PRODUCT VARIANT
                        if mahsulot_variant_id and mahsulot_variant_id != 'new':
                            variant = m.ProductVariant.objects.get(id=mahsulot_variant_id)
                            variant.stock += soni_int
                            variant.save()
                            variant_info = f"{variant.rang} - {variant.razmer}"
                        else:
                            variant, created = m.ProductVariant.objects.get_or_create(
                                product=mahsulot,
                                rang=variant_rang,
                                razmer=variant_razmer,
                                defaults={
                                    'stock': soni_int,
                                    'price': mahsulot.narxi
                                }
                            )
                            if not created:
                                variant.stock += soni_int
                                variant.save()
                            variant_info = f"🆕 {variant_rang or 'Rangsiz'} - {variant_razmer or 'Razmersiz'}"

                        # KOSIB JARAYON XOMASHYO
                        kosib_xomashyo = self._get_or_create_jarayon_xomashyo(
                            mahsulot=mahsulot,
                            category_name='kosib',
                            miqdor=Decimal(soni_int)
                        )

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=kosib_xomashyo,
                            miqdor=Decimal(soni_int)
                        )

                        mahsulot.refresh_from_db()

                        messages.warning(
                            request,
                            f"⚠️ MUSTAQIL ISH: {ishchi.ism}ga {mahsulot.nomi} x{soni_int} (Kosib) "
                            f"zakatovka xomashyosiz qo'shildi!\n"
                            f"🎨 Variant: {variant_info}\n"
                            f"🔶 {padoj.nomi}: -{soni_int} dona\n"
                            f"📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"
                        )

                    # Standart ish - zakatovka bilan
                    else:
                        if not zakatovka_xomashyo_id:
                            raise ValueError(
                                "❌ Zakatovka xomashyosi tanlanmagan! "
                                "'Mustaqil ish' belgisini yoqing yoki zakatovka xomashyosini tanlang."
                            )

                        # ZAKATOVKA
                        zakatovka = Xomashyo.objects.get(
                            id=zakatovka_xomashyo_id,
                            category__name__iexact='zakatovka',
                            mahsulot=mahsulot,
                            holati='active'
                        )

                        if zakatovka.miqdori < soni_int:
                            raise ValueError(
                                f"❌ Yetarli zakatovka yo'q! "
                                f"Kerak: {soni_int}, Mavjud: {zakatovka.miqdori}"
                            )

                        # PADOJ
                        padoj = Xomashyo.objects.get(
                            id=padoj_xomashyo_id,
                            holati='active'
                        )

                        padoj_variant = None
                        if padoj_variant_id:
                            padoj_variant = XomashyoVariant.objects.get(
                                id=padoj_variant_id,
                                xomashyo=padoj
                            )
                            if padoj_variant.miqdori < soni_int:
                                raise ValueError(
                                    f"❌ Padoj variantida yetarli miqdor yo'q! "
                                    f"Kerak: {soni_int}, Mavjud: {padoj_variant.miqdori}"
                                )
                            padoj_variant.miqdori -= Decimal(soni_int)
                            padoj_variant.save(update_fields=['miqdori'])
                        else:
                            if padoj.miqdori < soni_int:
                                raise ValueError(
                                    f"❌ Yetarli {padoj.nomi} yo'q! "
                                    f"Kerak: {soni_int}, Mavjud: {padoj.miqdori}"
                                )
                            padoj.miqdori -= Decimal(soni_int)
                            padoj.save(update_fields=['miqdori', 'updated_at'])

                        # ISH YARATISH
                        ish = m.Ish.objects.create(
                            ishchi=ishchi,
                            mahsulot=mahsulot,
                            soni=soni_int,
                            status='yangi',
                            sana=ish_sana_obj
                        )

                        # ZAKATOVKA CHIQIMI
                        zakatovka.miqdori -= Decimal(soni_int)
                        zakatovka.save(update_fields=['miqdori', 'updated_at'])

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=zakatovka,
                            miqdor=Decimal(soni_int)
                        )

                        # PADOJ CHIQIMI
                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=padoj,
                            variant=padoj_variant,
                            miqdor=Decimal(soni_int)
                        )

                        # PRODUCT VARIANT
                        if mahsulot_variant_id and mahsulot_variant_id != 'new':
                            variant = m.ProductVariant.objects.get(id=mahsulot_variant_id)
                            variant.stock += soni_int
                            variant.save()
                            variant_info = f"{variant.rang} - {variant.razmer}"
                        else:
                            variant, created = m.ProductVariant.objects.get_or_create(
                                product=mahsulot,
                                rang=variant_rang,
                                razmer=variant_razmer,
                                defaults={
                                    'stock': soni_int,
                                    'price': mahsulot.narxi
                                }
                            )
                            if not created:
                                variant.stock += soni_int
                                variant.save()
                            variant_info = f"🆕 {variant_rang or 'Rangsiz'} - {variant_razmer or 'Razmersiz'}"

                        # KOSIB JARAYON XOMASHYO
                        kosib_xomashyo = self._get_or_create_jarayon_xomashyo(
                            mahsulot=mahsulot,
                            category_name='kosib',
                            miqdor=Decimal(soni_int)
                        )

                        IshXomashyo.objects.create(
                            ish=ish,
                            xomashyo=kosib_xomashyo,
                            miqdor=Decimal(soni_int)
                        )

                        mahsulot.refresh_from_db()

                        messages.success(
                            request,
                            f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} (Kosib) qo'shildi!\n"
                            f"🎨 Variant: {variant_info}\n"
                            f"🔶 Zakatovka: -{soni_int} dona\n"
                            f"🔶 {padoj.nomi}: -{soni_int} dona\n"
                            f"📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"
                        )

                # ============================================================
                # PARDOZ VA BOSHQALAR
                # ============================================================
                else:
                    ish = m.Ish.objects.create(
                        ishchi=ishchi,
                        mahsulot=mahsulot,
                        soni=soni_int,
                        status='yangi',
                        sana=ish_sana_obj
                    )

                    messages.success(
                        request,
                        f"✅ {ishchi.ism}ga {mahsulot.nomi} x{soni_int} qo'shildi!\n"
                        f"📅 Sana: {ish_sana_obj.strftime('%d.%m.%Y')}"
                    )
                    
                from django.db import connection

                logger.info("FK CHECK: about to run")  # <-- shuni ko‘rishingiz shart

                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA foreign_key_check;")
                    rows = cursor.fetchall()

                print("FK CHECK rows:", rows)          # <-- konsolda ko‘rinadi
                logger.error("FK CHECK rows: %s", rows)

        except m.Ishchi.DoesNotExist:
            messages.error(request, "❌ Ishchi topilmadi!")
        except m.Product.DoesNotExist:
            messages.error(request, "❌ Mahsulot topilmadi!")
        except Xomashyo.DoesNotExist:
            messages.error(request, "❌ Xomashyo topilmadi!")
        except XomashyoVariant.DoesNotExist:
            messages.error(request, "❌ Xomashyo varianti topilmadi!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"❌ Xatolik: {str(e)}")
            print(traceback.format_exc())
        except Exception as e:
            logger.exception("IshQoshishView POST error")  # <-- traceback bilan log
            messages.error(request, f"❌ Xatolik: {str(e)}")
            print(traceback.format_exc())
            
        return redirect('main:ish_qoshish')

    @staticmethod
    def _get_or_create_jarayon_xomashyo(
        mahsulot: m.Product,
        category_name: str,
        miqdor: Decimal,
        rang: str = None
    ) -> Xomashyo:
        """Jarayon xomashyosini yaratish/yangilash"""
        category, _ = XomashyoCategory.objects.get_or_create(
            name=category_name,
            defaults={'turi': 'process'}
        )

        filters = {
            'mahsulot': mahsulot,
            'category': category,
            'olchov_birligi': 'dona'
        }

        if rang:
            filters['rang'] = rang

        xomashyo = Xomashyo.objects.filter(**filters).first()

        if xomashyo:
            xomashyo.miqdori += miqdor
            xomashyo.save(update_fields=['miqdori', 'updated_at'])
        else:
            xomashyo = Xomashyo.objects.create(
                mahsulot=mahsulot,
                category=category,
                nomi=f"{mahsulot.nomi} - {category_name.title()}",
                miqdori=miqdor,
                olchov_birligi='dona',
                holati='active',
                rang=rang
            )

        return xomashyo


#  SOTUVLAR 

class SotuvListView(AdminRequiredMixin, ListView):
    """Sotuvlar ro'yxati"""
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
                Q(xaridor__telefon__icontains=search) |
                Q(id__icontains=search)
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
        
        return queryset.select_related('xaridor').prefetch_related('items__variant__product')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()
        
        # Statistika
        context['bugungi_sotuv'] = m.Sotuv.objects.filter(
            sana__date=today
        ).aggregate(Sum('yakuniy_summa'))['yakuniy_summa__sum'] or 0
        
        context['bugungi_soni'] = m.Sotuv.objects.filter(
            sana__date=today
        ).count()
        
        context['oylik_sotuv'] = m.Sotuv.objects.filter(
            sana__year=today.year,
            sana__month=today.month
        ).aggregate(Sum('yakuniy_summa'))['yakuniy_summa__sum'] or 0
        
        context['jami_sotuv'] = m.Sotuv.objects.aggregate(
            Sum('yakuniy_summa')
        )['yakuniy_summa__sum'] or 0
        
        # Form uchun ma'lumotlar
        context['xaridorlar'] = m.Xaridor.objects.all().order_by('-created_at')[:20]
        context['mahsulotlar'] = m.ProductVariant.objects.filter(
            stock__gt=0
        ).select_related('product').order_by('product__nomi')
        context['is_admin'] = is_admin(self.request.user)
        
        return context

class SotuvDetailView(AdminRequiredMixin,DetailView):
    model = m.Sotuv
    template_name = "sotuv/sotuv.html"
    

@login_required(login_url='login')
@user_passes_test(is_admin, login_url="login")
def sotuv_qoshish(request):
    """Yangi sotuv yaratish (bir nechta mahsulot bilan)"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Xaridorni aniqlash
                xaridor_turi = request.POST.get('xaridor_turi')
                
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
                
                # 2. Asosiy sotuvni yaratish
                chegirma = request.POST.get('chegirma', 0)
                izoh = request.POST.get('izoh', '')
                tolov_holati = request.POST.get('tolov_holati', 'tolandi')
                
                sotuv = m.Sotuv.objects.create(
                    xaridor=xaridor,
                    chegirma=Decimal(str(chegirma)) if chegirma else 0,
                    izoh=izoh,
                    tolov_holati=tolov_holati
                )
                
                # 3. Mahsulotlarni qo'shish (frontenddan JSON formatda keladi)
                items_json = request.POST.get('items')
                if not items_json:
                    # Eski format - bitta mahsulot
                    variant_id = request.POST.get('mahsulot')
                    miqdor = request.POST.get('miqdor')
                    narx = request.POST.get('narx')
                    
                    if not all([variant_id, miqdor, narx]):
                        raise ValueError('Mahsulot, miqdor va narx majburiy!')
                    
                    variant = get_object_or_404(m.ProductVariant, id=variant_id)
                    
                    m.SotuvItem.objects.create(
                        sotuv=sotuv,
                        mahsulot=variant.product,
                        variant=variant,
                        miqdor=int(miqdor),
                        narx=Decimal(str(narx))
                    )
                else:
                    # Yangi format - bir nechta mahsulot
                    items = json.loads(items_json)
                    
                    for item in items:
                        variant = get_object_or_404(m.ProductVariant, id=item['variant_id'])
                        
                        m.SotuvItem.objects.create(
                            sotuv=sotuv,
                            mahsulot=variant.product,
                            variant=variant,
                            miqdor=int(item['miqdor']),
                            narx=Decimal(str(item['narx']))
                        )
                
                # 4. Summani yangilash (SotuvItem.save() da avtomatik bo'ladi)
                sotuv.refresh_from_db()
                
                messages.success(
                    request,
                    f"✅ Sotuv #{sotuv.id} muvaffaqiyatli yaratildi! "
                    f"Summa: {sotuv.yakuniy_summa:,.0f} so'm"
                )
                
                return redirect('main:sotuvlar')
                
        except ValueError as e:
            messages.error(request, f'❌ Xatolik: {str(e)}')
        except Exception as e:
            messages.error(request, f'❌ Kutilmagan xatolik: {str(e)}')
    
    return redirect('main:sotuvlar')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url="login")
def sotuv_item_qoshish(request, sotuv_id):
    """Mavjud sotuvga yangi mahsulot qo'shish"""
    if request.method == 'POST':
        try:
            sotuv = get_object_or_404(m.Sotuv, id=sotuv_id)
            
            variant_id = request.POST.get('variant_id')
            miqdor = request.POST.get('miqdor')
            narx = request.POST.get('narx')
            
            if not all([variant_id, miqdor, narx]):
                return JsonResponse({
                    'success': False, 
                    'error': 'Barcha maydonlarni to\'ldiring!'
                })
            
            variant = get_object_or_404(m.ProductVariant, id=variant_id)
            
            item = m.SotuvItem.objects.create(
                sotuv=sotuv,
                mahsulot=variant.product,
                variant=variant,
                miqdor=int(miqdor),
                narx=Decimal(str(narx))
            )
            
            sotuv.refresh_from_db()
            
            return JsonResponse({
                'success': True,
                'message': 'Mahsulot qo\'shildi!',
                'item_id': item.id,
                'jami_summa': float(sotuv.jami_summa),
                'yakuniy_summa': float(sotuv.yakuniy_summa)
            })
            
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Xatolik: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Faqat POST so\'rov qabul qilinadi'})


@login_required(login_url='login')
@user_passes_test(is_admin, login_url="login")
def sotuv_item_tahrirlash(request, item_id):
    """Sotuv itemini tahrirlash (narx va miqdorni)"""
    if request.method == 'POST':
        try:
            item = get_object_or_404(m.SotuvItem, id=item_id)
            
            narx = request.POST.get('narx')
            miqdor = request.POST.get('miqdor')
            
            if narx:
                item.narx = Decimal(str(narx))
            if miqdor:
                item.miqdor = int(miqdor)
            
            item.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Yangilandi!',
                'jami': float(item.jami),
                'sotuv_summa': float(item.sotuv.yakuniy_summa)
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Faqat POST so\'rov'})


@login_required(login_url='login')
@user_passes_test(is_admin, login_url="login")
def sotuv_item_ochirish(request, item_id):
    """Sotuv itemini o'chirish"""
    if request.method == 'POST':
        try:
            item = get_object_or_404(m.SotuvItem, id=item_id)
            sotuv = item.sotuv
            
            item.delete()
            sotuv.refresh_from_db()
            
            messages.success(request, 'Mahsulot o\'chirildi!')
            return redirect('main:sotuv_detail', pk=sotuv.id)
            
        except Exception as e:
            messages.error(request, f'Xatolik: {str(e)}')
    
    return redirect('main:sotuvlar')


@login_required(login_url='login')
@user_passes_test(is_admin, login_url="login")
def sotuv_ochirish(request, sotuv_id):
    """Butun sotuvni o'chirish"""
    if request.method == 'POST':
        try:
            with transaction.atomic():
                sotuv = get_object_or_404(m.Sotuv, id=sotuv_id)
                
                # Itemlarni o'chirish (stock qaytariladi)
                for item in sotuv.items.all():
                    item.delete()
                
                # Sotuvni o'chirish
                sotuv.delete()
                
                messages.success(request, 'Sotuv o\'chirildi!')
                
        except Exception as e:
            messages.error(request, f'Xatolik: {str(e)}')
    
    return redirect('main:sotuvlar')


@login_required(login_url='login')
def get_variant_info(request, variant_id):
    """Variant ma'lumotlarini olish (AJAX uchun)"""
    try:
        variant = get_object_or_404(m.ProductVariant, id=variant_id)
        
        return JsonResponse({
            'success': True,
            'narx': float(variant.price),
            'stock': variant.stock,
            'nomi': str(variant)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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
        
        return queryset.select_related('xaridor',  'sotuv')
    
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
            xaridor.jami_xarid = xaridor.sotuvlar.aggregate(
                Sum('jami_summa')
            )['jami_summa__sum'] or 0
            xaridor.xaridlar_soni = xaridor.sotuvlar.count()
        
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
        
        context['sotuvlar'] = xaridor.sotuvlar.prefetch_related(
            'items__mahsulot', 
            'items__variant'
        ).order_by('-sana')
        
        context['jami_xarid'] = xaridor.sotuvlar.aggregate(
            Sum('jami_summa')
        )['jami_summa__sum'] or 0
        
        context['xaridlar_soni'] = xaridor.sotuvlar.count()
        

        
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



