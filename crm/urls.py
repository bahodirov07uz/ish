
from django.contrib import admin
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static

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
    
    #sotuvlar
    path('sotuvlar/', views.SotuvListView.as_view(), name='sotuvlar'),
    path('sotuvlar/qoshish/', views.sotuv_qoshish, name='sotuv_qoshish'),
    path('sotuvlar/<int:pk>/ochirish/', views.sotuv_ochirish, name='sotuv_ochirish'),
    
    # Kirimlar
    path('kirimlar/', views.KirimListView.as_view(), name='kirimlar'),
    path("api/products/create/", views.ProductCreateView.as_view()),

    # Xaridorlar
    path('xaridorlar/', views.XaridorListView.as_view(), name='xaridorlar'),
    path('xaridorlar/<int:pk>/', views.XaridorDetailView.as_view(), name='xaridor_detail'),
    path('xaridorlar/qoshish/', views.xaridor_qoshish, name='xaridor_qoshish'),
    path('xaridorlar/<int:pk>/tahrirlash/', views.xaridor_tahrirlash, name='xaridor_tahrirlash'),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

