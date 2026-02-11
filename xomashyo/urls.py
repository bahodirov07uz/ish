
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

    path('xomashyolar/', views.XomashyolarListView.as_view(), name='xomashyolar'),
    path('xomashyo/<int:pk>/', views.XomashyoDetailView.as_view(), name='xomashyo_detail'),

    path('jarayon-hisobot/', views.jarayon_xomashyo_hisobot, name='jarayon_hisobot'),

    path('taminlash/', views.TaminlashView.as_view(), name='taminlash'),
    path('taminlash/qoshish/', views.TaminlashQushishView.as_view(), name='taminlash_qoshish'),
    path('taminlash/<int:taminlash_id>/', views.TaminlashDetailView.as_view(), name='taminlash_detail'),
    path('taminlash/<int:taminlash_id>/qaytarish/', views.TaminlashQaytarishView.as_view(), name='taminlash_qaytarish'),
    path('taminlash/item/<int:item_id>/qaytarish/', views.TaminlashItemQaytarishView.as_view(), name='taminlash_item_qaytarish'),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

