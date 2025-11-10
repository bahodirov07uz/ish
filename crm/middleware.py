"""
Security Middleware
URL orqali kirish urinishlarini bloklash
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve


class AdminOnlyMiddleware:
    """
    Faqat admin sahifalariga URL orqali kirishni bloklaydi
    """
    
    # Faqat admin uchun URL patternlar
    ADMIN_ONLY_URLS = [
        'main:employee_create',
        'main:employee_update',
        'main:employee_delete',
        'main:oylik_yopish',
        'main:yangi_oy',
        'main:ish_qoshish',
        'main:sotuv_ochirish',
        'main:xaridor_tahrirlash',
        'xomashyo:chiqimlar',
        'xomashyo:chiqim_qoshish',
        'xomashyo:chiqim_ochirish',
    ]
    
    # Login qilish shart bo'lgan URL'lar
    LOGIN_REQUIRED_URLS = [
        'main:home',
        'main:employee',
        'main:employee_detail',
        'main:products',
        'main:sotuvlar',
        'main:sotuv_qoshish',
        'main:kirimlar',
        'main:xaridorlar',
        'main:xaridor_detail',
        'main:xaridor_qoshish',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # URL ni aniqlash
        try:
            current_url = resolve(request.path_info).url_name
            current_namespace = resolve(request.path_info).namespace
            full_url = f"{current_namespace}:{current_url}" if current_namespace else current_url
        except:
            # URL topilmasa, keyingi middleware'ga o'tkazamiz
            return self.get_response(request)
        
        # Login tekshiruvi
        if full_url in self.LOGIN_REQUIRED_URLS:
            if not request.user.is_authenticated:
                messages.error(request, '❌ Iltimos avval tizimga kiring!')
                return redirect('login')
        
        # Admin tekshiruvi
        if full_url in self.ADMIN_ONLY_URLS:
            if not request.user.is_authenticated:
                messages.error(request, '❌ Iltimos avval tizimga kiring!')
                return redirect('login')
            
            if not (request.user.is_staff or request.user.is_superuser):
                messages.error(request, '❌ Sizda bu sahifaga kirish huquqi yo\'q!')
                return redirect('main:home')
        
        response = self.get_response(request)
        return response


class SecurityHeadersMiddleware:
    """
    Xavfsizlik headerlari qo'shish
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # XSS himoyasi
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response