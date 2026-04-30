from django.contrib import admin

from .models import Xomashyo,XomashyoHarakat,YetkazibBeruvchi,XomashyoCategory,XomashyoVariant
from resources import XomashyoResource,XomashyoHarakatResource
from import_export.admin import ImportExportModelAdmin
from crm.periodfilter import Last15DaysFilter

@admin.action(description="Tanlanganlarni tasdiqlash")
def make_approved(modeladmin, request, queryset):
    queryset.update(status="tasdiqlandi")


@admin.action(description="Tanlanganlarni bekor qilish")
def make_cancelled(modeladmin, request, queryset):
    queryset.update(status="bekor")
    
    
@admin.register(Xomashyo)
class XomashyoAdmin(ImportExportModelAdmin):
    resource_class = XomashyoResource
    list_display = ('nomi', 'category', 'miqdori', 'holati')
    list_filter = ('category', 'holati')
    search_fields = ('nomi',)

@admin.register(XomashyoHarakat)
class XomashyoHarakatAdmin(ImportExportModelAdmin):
    resource_class = XomashyoHarakatResource
    list_display = ("xomashyo","harakat_turi","miqdori","sana","jami_narx_uzs")
    list_filter = ("harakat_turi","sana",Last15DaysFilter)

admin.site.register(YetkazibBeruvchi)

admin.site.register(XomashyoCategory)
admin.site.register(XomashyoVariant)
