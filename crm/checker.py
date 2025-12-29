
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Xomashyo, XomashyoVariant
import logging

@require_http_methods(["GET"])
def get_zakatovka_xomashyolar_api(request, mahsulot_id):
    """Mahsulot uchun zakatovka xomashyolarini olish"""
    try:
        xomashyolar = Xomashyo.objects.filter(
            mahsulot_id=mahsulot_id,
            category__name__iexact='zakatovka',
            holati='active',
            miqdori__gt=0
        ).values('id', 'nomi', 'miqdori', 'olchov_birligi')
        
        return JsonResponse({
            'success': True,
            'xomashyolar': list(xomashyolar)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


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

@require_http_methods(["GET"])
def get_kroy_xomashyolar_api(request, mahsulot_id):
    """
    Mahsulot uchun kroy (kesilgan yarim tayyor mahsulot) xomashyolarini olish
    URL: /api/mahsulot/<mahsulot_id>/kroy-xomashyolar/
    """
    try:
        # Mahsulotga tegishli kroy xomashyolarini filterlash
        xomashyolar = Xomashyo.objects.filter(
            mahsulot_id=mahsulot_id,
            category__name__iexact='kroy', # Kroy kategoriyasi
            category__turi='process',      # Yarim tayyor mahsulot turi
            holati='active',
            miqdori__gt=0
        ).values('id', 'nomi', 'miqdori', 'olchov_birligi')
        
        xomashyolar_list = []
        for x in xomashyolar:
            xomashyolar_list.append({
                'id': x['id'],
                'nomi': x['nomi'],
                'miqdori': str(x['miqdori']),
                'olchov_birligi': dict(Xomashyo.OLCHOV_BIRLIKLARI).get(x['olchov_birligi'], x['olchov_birligi'])
            })
        
        return JsonResponse({
            'success': True,
            'xomashyolar': xomashyolar_list
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

