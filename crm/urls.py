
from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from . import checker
import chek
app_name = "main"

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('oylik_yopish/<int:pk>/', views.oylik_yopish, name='oylik_yopish'),
    path('yangi_oy_boshlash/<int:pk>/',views.yangi_oy_boshlash, name='yangi_oy'),
    
    path("employees/",views.EmployeeView.as_view(),name="employee"),
    path("employees/<int:pk>/",views.EmployeeDetailView.as_view(),name="employee_detail"),
    path('employees/create/', views.EmployeeCreateView.as_view(), name='ishchi_create'),
    path('employees/<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='ishchi_delete'),
    path('employees/<int:pk>/update/', views.EmployeeUpdateView.as_view(), name='ishchi_update'),
    
    path("products/",views.ProductsView.as_view(),name="products"),
    
    path('ish-qoshish/', views.IshQoshishView.as_view(), name='ish_qoshish'),
    
    # sotuvlar
    path('sotuvlar/', views.SotuvQoshish.as_view(), name='sotuvlar'),
    path('sotuv/list/',views.SotuvListView.as_view(),name="sotuv_list"),
    path('sotuv/qoshish/', views.sotuv_qoshish, name='sotuv_qoshish'),
    path('sotuv/<int:sotuv_id>/ochirish/', views.sotuv_ochirish, name='sotuv_ochirish'),
    path('sotuv/detail/<int:pk>/',views.SotuvDetailView.as_view(),name="sotuv_detail"),
    path('sotuv/<int:sotuv_id>/pdf/', views.sotuv_pdf, name='sotuv_pdf'),


    # Sotuv itemlari
    path('sotuv/<int:sotuv_id>/item/qoshish/', views.sotuv_item_qoshish, name='sotuv_item_qoshish'),
    path('sotuv/item/<int:item_id>/tahrirlash/', views.sotuv_item_tahrirlash, name='sotuv_item_tahrirlash'),
    path('sotuv/item/<int:item_id>/ochirish/', views.sotuv_item_ochirish, name='sotuv_item_ochirish'),
    path('api/variant/<int:variant_id>/', views.get_variant_info, name='get_variant_info'),

    # Kirimlar
    path('kirimlar/', views.KirimListView.as_view(), name='kirimlar'),
    path('kirim/qoshish/', views.kirim_qoshish, name='kirim_qoshish'),

    # Xaridorlar
    path('xaridorlar/', views.XaridorListView.as_view(), name='xaridorlar'),
    path('xaridorlar/<int:pk>/', views.XaridorDetailView.as_view(), name='xaridor_detail'),
    path('xaridorlar/qoshish/', views.xaridor_qoshish, name='xaridor_qoshish'),
    path('xaridorlar/<int:pk>/tahrirlash/', views.xaridor_tahrirlash, name='xaridor_tahrirlash'),
    
    
    path('xaridorlar/<int:pk>/umumiy-chek/',
    chek.XaridorUmumiyChekView.as_view(),
    name='xaridor_umumiy_chek'),
    path('ishchilar/<int:pk>/chek/', chek.IshchiChekView.as_view(), name='ishchi_chek'),

    # Checking
    
    path(
        'api/mahsulot/<int:mahsulot_id>/zakatovka-xomashyolar/',
        checker.get_zakatovka_xomashyolar_api,
        name='api_zakatovka_xomashyolar'
    ),
    path(
        'api/xomashyo/<int:xomashyo_id>/variants/',
        checker.get_xomashyo_variants_api,
        name='api_xomashyo_variants'
    ),
    path('api/mahsulot/<int:mahsulot_id>/variants/', 
            checker.get_product_variants, 
            name='get_product_variants'),
    path('api/mahsulot/<int:mahsulot_id>/kroy-xomashyolar/', 
        checker.get_kroy_xomashyolar_api, 
        name='get_kroy_xomashyolar'),
    path('api/usd-kurs/',views.get_usd_kurs,name="usd_kurs")
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# crm/urls.py ga qo'shish kerak bo'lgan qatorlar:
from django.urls import path
from .excel.excel import excel_shablon, excel_parse, excel_saqlash,excel_ish_sahifa

from .excel.excel import excel_shablon, excel_parse, excel_saqlash, excel_ish_sahifa

urlpatterns += [
    path('excel/',                        excel_ish_sahifa, name='excel_ish'),
    path('excel/shablon/<int:ishchi_id>/', excel_shablon,   name='excel_shablon'),
    path('excel/parse/<int:ishchi_id>/',   excel_parse,     name='excel_parse'),
    path('excel/saqlash/<int:ishchi_id>/', excel_saqlash,   name='excel_saqlash'),
]