
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods,require_GET
from django.views.decorators.csrf import csrf_exempt
from .models import ProductVariant
from xomashyo.models import Xomashyo, XomashyoVariant

import logging

@require_http_methods(["GET"])
def get_zakatovka_xomashyolar_api(request, mahsulot_id):
    """
    Zakatovka jarayon xomashyolarini olish.
 
    ESKI: faqat mahsulot_id=mahsulot_id bo'lgan xomashyolar qaytardi.
 
    YANGI: BARCHA faol zakatovka xomashyolari qaytariladi (istalgan
    mahsulotga tegishli bo'lsin). So'ralgan mahsulotga tegishli
    bo'lgani `is_current: true` bilan belgilanadi va ro'yxat
    boshiga chiqariladi — frontend buni default tanlaydi, lekin
    foydalanuvchi xohlasa boshqasini ham tanlashi mumkin.
    """
    try:
        xomashyolar = Xomashyo.objects.filter(
            category__name__iexact='zakatovka',
            holati='active',
            miqdori__gt=0
        ).values('id', 'nomi', 'miqdori', 'olchov_birligi', 'mahsulot_id')
 
        xomashyolar_list = []
        for x in xomashyolar:
            xomashyolar_list.append({
                'id': x['id'],
                'nomi': x['nomi'],
                'miqdori': x['miqdori'],
                'olchov_birligi': x['olchov_birligi'],
                'is_current': (str(x['mahsulot_id']) == str(mahsulot_id)),
            })
 
        # Joriy mahsulotga tegishlilarni ro'yxat boshiga chiqarish
        xomashyolar_list.sort(key=lambda i: (not i['is_current'], i['nomi']))
 
        return JsonResponse({
            'success': True,
            'xomashyolar': xomashyolar_list
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
 
 
@require_http_methods(["GET"])
def get_kroy_xomashyolar_api(request, mahsulot_id):
    """
    Mahsulot uchun kroy (kesilgan yarim tayyor mahsulot) xomashyolarini olish
    URL: /api/mahsulot/<mahsulot_id>/kroy-xomashyolar/
 
    ESKI: faqat mahsulot_id=mahsulot_id bo'lgan kroy xomashyolarini qaytarardi.
 
    YANGI: BARCHA faol kroy xomashyolari qaytariladi. So'ralgan
    mahsulotga tegishli bo'lgani `is_current: true` bilan belgilanadi
    va ro'yxat boshiga chiqariladi.
    """
    try:
        xomashyolar = Xomashyo.objects.filter(
            category__name__iexact='kroy',       # Kroy kategoriyasi
            category__turi='process',             # Yarim tayyor mahsulot turi
            holati='active',
            miqdori__gt=0
        ).values('id', 'nomi', 'miqdori', 'olchov_birligi', 'mahsulot_id')
 
        xomashyolar_list = []
        for x in xomashyolar:
            xomashyolar_list.append({
                'id': x['id'],
                'nomi': x['nomi'],
                'miqdori': str(x['miqdori']),
                'olchov_birligi': dict(Xomashyo.OLCHOV_BIRLIKLARI).get(x['olchov_birligi'], x['olchov_birligi']),
                'is_current': (str(x['mahsulot_id']) == str(mahsulot_id)),
            })
 
        # Joriy mahsulotga tegishlilarni ro'yxat boshiga chiqarish
        xomashyolar_list.sort(key=lambda i: (not i['is_current'], i['nomi']))
 
        return JsonResponse({
            'success': True,
            'xomashyolar': xomashyolar_list
        })
 
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
 
 
# ================================================================
# O'ZGARMAGAN — faqat fayl butunligi uchun to'liq keltirildi
# ================================================================
 
@require_http_methods(["GET"])
def get_xomashyo_variants_api(request, xomashyo_id):
    """Xomashyo variantlarini olish"""
    try:
        xomashyo = Xomashyo.objects.get(id=xomashyo_id)
 
        variants = XomashyoVariant.objects.filter(
            xomashyo=xomashyo,
            miqdori__gt=0
        ).values('id', 'rang', 'qalinlik', 'partiya_kodi', 'miqdori', 'narxi')
 
        return JsonResponse({
            'success': True,
            'has_variants': variants.exists(),
            'variants': list(variants),
            'xomashyo': {
                'id': xomashyo.id,
                'nomi': xomashyo.nomi,
                'miqdori': float(xomashyo.miqdori),
                'olchov_birligi': xomashyo.get_olchov_birligi_display()
            }
        })
    except Xomashyo.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Xomashyo topilmadi!'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
 
 
@require_GET
def get_product_variants(request, mahsulot_id):
    """Mahsulot variantlarini olish"""
    try:
        variants = ProductVariant.objects.filter(
            product_id=mahsulot_id
        ).order_by('-stock')
 
        data = {
            'success': True,
            'variants': [
                {
                    'id': v.id,
                    'rang': v.rang,
                    'razmer': v.razmer,
                    'stock': v.stock,
                    'price': float(v.price),
                }
                for v in variants
            ]
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
 
 