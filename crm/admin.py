from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from import_export.admin import ImportExportModelAdmin
from import_export.admin import ExportMixin
from .models import (
    Category, Product, ProductVariant, IshchiCategory, Ishchi,
    Oyliklar, EskiIsh, Ish, ChiqimTuri, Chiqim, Xaridor, Sotuv, Kirim,IshXomashyo,Feature,Avans,TeriSarfi,SotuvItem,ChiqimItem
)

from resources import IshchiResource,ProductResource,ProductVariantResource,IshResource,ChiqimResource,SotuvResource,SotuvItemResource
from crm.periodfilter import Last15DaysFilter

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    readonly_fields = ('sku', 'barcode')
    
    
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 20

@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    inlines = [ProductVariantInline]
    resource_class = ProductResource
    list_display = ('nomi', 'category', 'narxi', 'status', 'created_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('nomi', 'description')
    readonly_fields = ('created_at', 'avg_profit')
    fieldsets = (
        ('Asosiy maʼlumotlar', {
            'fields': ('nomi', 'category', 'description', 'status', 'image')
        }),
        ('Narxlar', {
            'fields': ('narxi', 'narx_kosib', 'narx_zakatovka', 'narx_kroy', 'narx_pardoz','narx_rezak')
        }),
        ('Inventar', {
            'fields': ( 'teri_sarfi', 'astar_sarfi', 'avg_profit')
        }),
        ('Qoshimcha', {
            'fields': ('created_at',)
        }),
    )
    list_per_page = 20
         
@admin.register(ProductVariant)
class ProductVariantAdmin(ImportExportModelAdmin):
    resource_class = ProductVariantResource
    list_display = ('product', 'stock', 'price','type','rang',"sku")
    list_filter = ('product','type')
    search_fields = ('product__nomi',)
    autocomplete_fields = ["product"]
    list_per_page = 20

@admin.register(IshchiCategory)
class IshchiCategoryAdmin(admin.ModelAdmin):
    list_display = ('nomi',)
    search_fields = ('nomi',)
    list_per_page = 20

@admin.register(Ishchi)
class IshchiAdmin(ImportExportModelAdmin):
    resource_class = IshchiResource
    search_fields = ['ism', 'telefon']

    list_display = ('ism', 'familiya', 'turi', 'maosh', 'telefon', 'is_active')
    list_filter = ('turi', 'is_active', 'is_oylik_open')
    search_fields = ('ism', 'familiya', 'telefon')
    readonly_fields = ('oylik_yopilgan_sana',)
    list_per_page = 20

@admin.register(Oyliklar)
class OyliklarAdmin(admin.ModelAdmin):
    list_display = ('ishchi', 'sana', 'oylik', 'yopilgan')
    autocomplete_fields = ["ishchi"]
    list_filter = ('sana', 'yopilgan')
    search_fields = ('ishchi__ism', 'ishchi__familiya')
    list_per_page = 20
    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "oylik":
            kwargs["widget"] = forms.TextInput(attrs={
                "class": "mask-money",
                "inputmode": "numeric",   # telefonda raqam klaviatura
                "autocomplete": "off",
                "style": "width: 300px; font-weight: bold;",
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

    class Media:
        js = ("js/money_mask.js",)

@admin.register(EskiIsh)
class EskiIshAdmin(admin.ModelAdmin):
    list_display = ('ishchi', 'mahsulot', 'sana', 'narxi', 'soni')
    list_filter = ('sana',)
    search_fields = ('ishchi__ism', 'mahsulot')
    list_per_page = 20

@admin.register(Ish)
class IshAdmin(ImportExportModelAdmin):
    resource_class = IshResource
    list_display = ('mahsulot', 'ishchi', 'sana', 'soni', 'narxi')
    list_filter = ('sana', 'ishchi__turi')
    search_fields = ('mahsulot__nomi', 'ishchi__ism')
    list_per_page = 20

@admin.register(ChiqimTuri)
class ChiqimTuriAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    list_per_page = 20

@admin.register(Avans)
class AvansAdmin(admin.ModelAdmin):
    list_display = ("ishchi", "amount")
    autocomplete_fields = ['ishchi']
    fields = ['ishchi', 'amount', 'created', 'ended', 'is_active']

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "amount":
            kwargs["widget"] = forms.TextInput(attrs={
                "class": "mask-money",
                "inputmode": "numeric",   # telefonda raqam klaviatura
                "autocomplete": "off",
                "style": "width: 300px; font-weight: bold;",
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

    class Media:
        js = ("js/money_mask.js",)
            

@admin.register(Chiqim)
class ChiqimAdmin(ExportMixin,admin.ModelAdmin):
    resource_class = ChiqimResource
    list_display = ('name', 'category', 'price', 'created')
    list_filter = ('category', Last15DaysFilter,'created')
    search_fields = ('name',)
    list_per_page = 20

@admin.register(Xaridor)
class XaridorAdmin(admin.ModelAdmin):
    list_display = ('ism', 'telefon', 'manzil', 'created_at')
    search_fields = ('ism', 'telefon')
    list_per_page = 20

class SotuvItemInline(admin.TabularInline):
    """Sotuv ichida itemlarni ko'rsatish"""
    model = SotuvItem
    extra = 1
    fields = ('mahsulot', 'variant', 'miqdor', 'narx', 'jami')
    readonly_fields = ('jami',)
    autocomplete_fields = ['variant', 'mahsulot']


@admin.register(Sotuv)
class SotuvAdmin(ImportExportModelAdmin):
    """Sotuv admin paneli"""
    resource_class = SotuvResource
    list_display = ('id', 'xaridor', 'jami_summa', 'chegirma', 'yakuniy_summa', 'tolov_holati', 'sana')
    list_filter = ('tolov_holati', 'sana')
    search_fields = ('xaridor__ism', 'xaridor__telefon', 'id')
    readonly_fields = ('jami_summa', 'yakuniy_summa', 'created_at', 'updated_at')
    date_hierarchy = 'sana'
    inlines = [SotuvItemInline]
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('xaridor', 'tolov_holati', 'sana')
        }),
        ('Summa', {
            'fields': ('jami_summa', 'chegirma', 'yakuniy_summa')
        }),
        ('Qo\'shimcha', {
            'fields': ('izoh', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('xaridor').prefetch_related('items')


@admin.register(SotuvItem)
class SotuvItemAdmin(ImportExportModelAdmin):
    """Sotuv item admin paneli"""
    resource_class = SotuvItemResource
    list_display = ('id', 'sotuv', 'variant', 'miqdor', 'narx', 'jami')
    list_filter = ('sotuv__sana',)
    search_fields = ('sotuv__id', 'mahsulot__nomi', 'variant__rang')
    readonly_fields = ('jami',)
    autocomplete_fields = ['sotuv', 'variant', 'mahsulot']
    date_hierarchy = 'sotuv__sana'

    fieldsets = (
        ('Sotuv', {
            'fields': ('sotuv',)
        }),
        ('Mahsulot', {
            'fields': ('mahsulot', 'variant')
        }),
        ('Narx va miqdor', {
            'fields': ('miqdor', 'narx', 'jami')
        }),
        ('Qo\'shimcha', {
            'fields': ('izoh',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'sotuv', 'mahsulot', 'variant'
        )
    
@admin.register(Kirim)
class KirimAdmin(admin.ModelAdmin):
    list_display = ( 'xaridor', 'summa', 'sana')
    list_filter = ('sana',)
    search_fields = ('xaridor__ism',)
    readonly_fields = ('summa', 'sana')
    list_per_page = 20

@admin.register(IshXomashyo)
class IshXomashyoAdmin(admin.ModelAdmin):
    list_display = ("ish","variant","miqdor")

    list_per_page = 20

admin.site.register(Feature)
admin.site.register(TeriSarfi)

# Admin sahifasini sozlash
admin.site.site_header = "CRM Tizimi"
admin.site.site_title = "CRM Admin"
admin.site.index_title = "Boshqaruv paneliga xush kelibsiz"