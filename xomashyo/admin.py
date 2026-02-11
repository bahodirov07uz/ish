from django.contrib import admin

from .models import Xomashyo,XomashyoHarakat,YetkazibBeruvchi,XomashyoCategory,XomashyoVariant,Taminlash,TaminlashItem
from resources import XomashyoResource,XomashyoHarakatResource
from import_export.admin import ImportExportModelAdmin
from crm.periodfilter import Last15DaysFilter
@admin.register(Xomashyo)
class XomashyoAdmin(ImportExportModelAdmin):
    resource_class = XomashyoResource
    list_display = ('nomi', 'category', 'miqdori', 'holati')
    list_filter = ('category', 'holati')
    search_fields = ('nomi',)

@admin.register(XomashyoHarakat)
class XomashyoHarakatAdmin(ImportExportModelAdmin):
    resource_class = XomashyoHarakatResource
    list_display = ("xomashyo","harakat_turi","miqdori","sana","narxi")
    list_filter = ("harakat_turi","sana",Last15DaysFilter)

admin.site.register(YetkazibBeruvchi)

admin.site.register(XomashyoCategory)
admin.site.register(XomashyoVariant)
admin.site.register(Taminlash)
admin.site.register(TaminlashItem)