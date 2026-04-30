
from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "xomashyo"

urlpatterns = [
    path('chiqimlar/', views.ChiqimListView.as_view(), name='chiqimlar'),
    path('chiqimlar/qoshish/', views.chiqim_qoshish, name='chiqim_qoshish'),
    path('chiqimlar/<int:pk>/ochirish/', views.chiqim_ochirish, name='chiqim_ochirish'),
    path('chiqim-ochirish/<int:chiqim_id>/', views.chiqim_ochirish, name='chiqim_ochirish'),
    
    path('kirim-ochirish/<int:harakat_id>/', views.xomashyo_kirim_ochirish, name='xomashyo_kirim_ochirish'),
    path('xomashyo-kirim/', views.xomashyo_kirim_qoshish, name='xomashyo_kirim_qoshish'),

    path('xomashyolar/', views.XomashyolarListView.as_view(), name='xomashyolar'),
    path('xomashyo/<int:pk>/', views.XomashyoDetailView.as_view(), name='xomashyo_detail'),

    path('jarayon-hisobot/', views.jarayon_xomashyo_hisobot, name='jarayon_hisobot'),

    path('yetkazib-beruvchilar/', views.YetkazibBeruvchilarView.as_view(), name='yb_list'),
    path('yetkazib-beruvchi/<int:yb_id>/', views.yetkazib_beruvchi_detail, name='yb_detail'),
    path('yetkazib-beruvchi/<int:yb_id>/avto-tolov/', views.yb_avto_tolov, name='yb_avto_tolov'),
    path('yetkazib-beruvchi/<int:yb_id>/harakat/<int:harakat_id>/tolov/', views.yb_harakat_tolov, name='yb_harakat_tolov'),


]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

