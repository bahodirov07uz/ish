from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path("",include("shop.urls")),
    path('uy', include('crm.urls')),
    path('xomashyo/', include('xomashyo.urls')),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('budget/', include('budget.urls')),
    path('accounts/', include('allauth.urls')),
    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

