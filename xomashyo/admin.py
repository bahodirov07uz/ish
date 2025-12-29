from django.contrib import admin

from .models import Xomashyo,XomashyoHarakat,YetkazibBeruvchi,XomashyoCategory,XomashyoVariant
from resources import XomashyoResource
from import_export.admin import ImportExportModelAdmin

@admin.register(Xomashyo)
class XomashyoAdmin(ImportExportModelAdmin):
    resource_class = XomashyoResource
    list_display = ('nomi', 'category', 'miqdori', 'holati')
    list_filter = ('category', 'holati')
    search_fields = ('nomi',)
admin.site.register(XomashyoHarakat)
admin.site.register(YetkazibBeruvchi)
admin.site.register(XomashyoCategory)
admin.site.register(XomashyoVariant)