
from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static

app_name = "xomashyo"

urlpatterns = [
    path('', views.ChiqimListView.as_view(), name='chiqimlar'),
    path('chiqimlar/qoshish/', views.chiqim_qoshish, name='chiqim_qoshish'),
    path('chiqimlar/<int:pk>/ochirish/', views.chiqim_ochirish, name='chiqim_ochirish'),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

