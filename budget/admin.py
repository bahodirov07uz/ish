# budget/admin.py
from django.contrib import admin
from django.db.models import Sum, Q
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal

from .models import Byudjet, ByudjetLimit, Tranzaksiya


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _fmt(val) -> str:
    """Decimal/float → chiroyli so'm formatida."""
    try:
        return f"{float(val):,.0f} so'm"
    except Exception:
        return "—"


def _progress_html(foiz: float, holat: str) -> str:
    colors = {
        'xavfsiz'   : '#059669',
        'ogoh'      : '#f59e0b',
        'xavfli'    : '#ef4444',
        'oshib_ketdi': '#dc2626',
    }
    color = colors.get(holat, '#7c3aed')
    width = min(foiz, 100)
    return format_html(
        '<div style="min-width:140px">'
        '<div style="height:8px;border-radius:4px;background:#e5e7eb;overflow:hidden;margin-bottom:3px">'
        '<div style="width:{w}%;height:100%;background:{c};border-radius:4px"></div>'
        '</div>'
        '<span style="font-size:11px;font-weight:700;color:{c}">{p}%</span>'
        '</div>',
        w=width, c=color, p=foiz,
    )


def _holat_badge(holat: str) -> str:
    cfg = {
        'xavfsiz'   : ('#f0fdf4', '#059669', '✅ Xavfsiz'),
        'ogoh'      : ('#fef3c7', '#b45309', '⚡ Ogoh'),
        'xavfli'    : ('#fef2f2', '#dc2626', '🔴 Xavfli'),
        'oshib_ketdi': ('#fef2f2', '#dc2626', '🚨 Oshib ketdi'),
    }
    bg, color, label = cfg.get(holat, ('#f3f4f6', '#6b7280', holat))
    return format_html(
        '<span style="background:{};color:{};padding:2px 9px;border-radius:5px;'
        'font-size:11px;font-weight:700">{}</span>',
        bg, color, label,
    )


# ─────────────────────────────────────────────────────────────────
# ByudjetLimit inline
# ─────────────────────────────────────────────────────────────────

class ByudjetLimitInline(admin.TabularInline):
    model  = ByudjetLimit
    extra  = 0
    fields = ('nomi', 'manba', 'kategoriya', 'limit_summa',
              '_haqiqiy_sarfi', '_foiz_bar', '_holat_col')
    readonly_fields = ('_haqiqiy_sarfi', '_foiz_bar', '_holat_col')
    show_change_link = False

    @admin.display(description="Haqiqiy sarfi")
    def _haqiqiy_sarfi(self, obj):
        return _fmt(obj.haqiqiy_sarfi) if obj.pk else "—"

    @admin.display(description="Foiz")
    def _foiz_bar(self, obj):
        if not obj.pk:
            return "—"
        return format_html(_progress_html(obj.foiz, obj.holat))

    @admin.display(description="Holat")
    def _holat_col(self, obj):
        if not obj.pk:
            return "—"
        return format_html(_holat_badge(obj.holat))


# ─────────────────────────────────────────────────────────────────
# Tranzaksiya inline (faqat ko'rish)
# ─────────────────────────────────────────────────────────────────



# ─────────────────────────────────────────────────────────────────
# Byudjet Admin
# ─────────────────────────────────────────────────────────────────

class ByudjetHolatFilter(admin.SimpleListFilter):
    title         = "Holat"
    parameter_name = "holat"

    def lookups(self, request, model_admin):
        return [
            ('faol',   '● Faol'),
            ('tugagan','✓ Tugagan'),
        ]

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'faol':
            return queryset.filter(davr_boshi__lte=today, davr_oxiri__gte=today)
        if self.value() == 'tugagan':
            return queryset.filter(davr_oxiri__lt=today)
        return queryset


@admin.register(Byudjet)
class ByudjetAdmin(admin.ModelAdmin):
    list_display  = (
        'nomi', '_davr', '_umumiy', '_jami_sarfi_col',
        '_qoldiq_col', '_foiz_bar', '_holat_col', '_faol_col',
    )
    list_filter   = (ByudjetHolatFilter,)
    search_fields = ('nomi', 'izoh')
    readonly_fields = (
        'yaratgan', 'created_at',
        '_stat_jami', '_stat_chiqim', '_stat_xomashyo', '_stat_qoldiq',
        '_stat_foiz',
    )
    fieldsets = (
        ("Asosiy", {
            'fields': ('nomi', 'davr_boshi', 'davr_oxiri', 'umumiy_summa', 'izoh'),
        }),
        ("Hisoblangan (avtomatik)", {
            'fields': (
                '_stat_jami', '_stat_chiqim',
                '_stat_xomashyo', '_stat_qoldiq', '_stat_foiz',
            ),
            'classes': ('collapse',),
        }),
        ("Meta", {
            'fields': ('yaratgan', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    inlines = [ByudjetLimitInline]
    ordering = ('-davr_boshi',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('yaratgan')

    # ── List columns ────────────────────────────────────────────

    @admin.display(description="Davr")
    def _davr(self, obj):
        return f"{obj.davr_boshi.strftime('%d.%m.%Y')} – {obj.davr_oxiri.strftime('%d.%m.%Y')}"

    @admin.display(description="Byudjet")
    def _umumiy(self, obj):
        return _fmt(obj.umumiy_summa)

    @admin.display(description="Sarflangan")
    def _jami_sarfi_col(self, obj):
        sarfi = obj.jami_sarfi
        return format_html(
            '<span style="font-weight:700;color:#dc2626">{}</span>', _fmt(sarfi)
        )

    @admin.display(description="Qoldiq")
    def _qoldiq_col(self, obj):
        q = obj.qoldiq
        color = '#059669' if q > 0 else '#dc2626'
        return format_html(
            '<span style="font-weight:700;color:{}">{}</span>', color, _fmt(q)
        )

    @admin.display(description="Foiz")
    def _foiz_bar(self, obj):
        return format_html(_progress_html(obj.sarfi_foiz, obj.holat))

    @admin.display(description="Holat")
    def _holat_col(self, obj):
        return format_html(_holat_badge(obj.holat))

    @admin.display(description="Faol?", boolean=True)
    def _faol_col(self, obj):
        return obj.is_active

    # ── Detail readonly fields ────────────────────────────────────

    @admin.display(description="Jami sarfi")
    def _stat_jami(self, obj):
        return _fmt(obj.jami_sarfi)

    @admin.display(description="Chiqim sarfi")
    def _stat_chiqim(self, obj):
        return _fmt(obj.chiqim_sarfi)

    @admin.display(description="Xomashyo sarfi")
    def _stat_xomashyo(self, obj):
        return _fmt(obj.xomashyo_sarfi)

    @admin.display(description="Qoldiq")
    def _stat_qoldiq(self, obj):
        return _fmt(obj.qoldiq)

    @admin.display(description="Sarfi foiz")
    def _stat_foiz(self, obj):
        return format_html(_progress_html(obj.sarfi_foiz, obj.holat))

    def save_model(self, request, obj, form, change):
        if not change:
            obj.yaratgan = request.user
        super().save_model(request, obj, form, change)


# ─────────────────────────────────────────────────────────────────
# ByudjetLimit Admin (mustaqil ham ko'rish uchun)
# ─────────────────────────────────────────────────────────────────

@admin.register(ByudjetLimit)
class ByudjetLimitAdmin(admin.ModelAdmin):
    list_display  = (
        'nomi', '_byudjet_link', 'manba', 'kategoriya',
        '_limit', '_sarfi', '_foiz_bar', '_holat_col',
    )
    list_filter   = ('manba', 'byudjet')
    search_fields = ('nomi', 'kategoriya', 'byudjet__nomi')
    autocomplete_fields = ('byudjet',)
    readonly_fields = ('_sarfi_ro', '_foiz_ro', '_holat_ro', '_qoldiq_ro')
    fieldsets = (
        ("Asosiy", {
            'fields': ('byudjet', 'nomi', 'manba', 'kategoriya', 'limit_summa'),
        }),
        ("Hisoblangan", {
            'fields': ('_sarfi_ro', '_foiz_ro', '_holat_ro', '_qoldiq_ro'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('byudjet')

    @admin.display(description="Byudjet")
    def _byudjet_link(self, obj):
        url = reverse('admin:budget_byudjet_change', args=[obj.byudjet_id])
        return format_html('<a href="{}">{}</a>', url, obj.byudjet.nomi)

    @admin.display(description="Limit")
    def _limit(self, obj):
        return _fmt(obj.limit_summa)

    @admin.display(description="Haqiqiy sarfi")
    def _sarfi(self, obj):
        return format_html(
            '<span style="font-weight:700;color:#dc2626">{}</span>',
            _fmt(obj.haqiqiy_sarfi)
        )

    @admin.display(description="Foiz")
    def _foiz_bar(self, obj):
        return format_html(_progress_html(obj.foiz, obj.holat))

    @admin.display(description="Holat")
    def _holat_col(self, obj):
        return format_html(_holat_badge(obj.holat))

    # Detail readonly
    @admin.display(description="Haqiqiy sarfi")
    def _sarfi_ro(self, obj): return _fmt(obj.haqiqiy_sarfi) if obj.pk else "—"

    @admin.display(description="Foiz")
    def _foiz_ro(self, obj): return format_html(_progress_html(obj.foiz, obj.holat)) if obj.pk else "—"

    @admin.display(description="Holat")
    def _holat_ro(self, obj): return format_html(_holat_badge(obj.holat)) if obj.pk else "—"

    @admin.display(description="Qoldiq")
    def _qoldiq_ro(self, obj): return _fmt(obj.qoldiq) if obj.pk else "—"


# ─────────────────────────────────────────────────────────────────
# Tranzaksiya Admin
# ─────────────────────────────────────────────────────────────────

class TranzaksiyaManbaFilter(admin.SimpleListFilter):
    title          = "Manba"
    parameter_name = "manba"

    def lookups(self, request, model_admin):
        return [('chiqim', 'Chiqim'), ('xomashyo', 'Xomashyo')]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(manba=self.value())
        return queryset


@admin.register(Tranzaksiya)
class TranzaksiyaAdmin(admin.ModelAdmin):
    list_display  = (
        'sana', '_manba_badge', 'nomi', 'kategoriya',
        '_summa_uzs', '_summa_usd', 'ishchi', '_manba_link',
    )
    list_filter   = (TranzaksiyaManbaFilter, 'sana', 'kategoriya')
    search_fields = ('nomi', 'kategoriya', 'ishchi__ism', 'ishchi__familiya')
    date_hierarchy = 'sana'
    readonly_fields = (
        'manba', 'chiqim', 'xomashyo_harakat',
        'ishchi', 'foydalanuvchi',
        'summa_uzs', 'summa_usd',
        'nomi', 'kategoriya', 'sana', 'created_at',
        '_manba_link',
    )
    fieldsets = (
        ("Tranzaksiya", {
            'fields': ('manba', 'sana', 'nomi', 'kategoriya'),
        }),
        ("Summalar", {
            'fields': ('summa_uzs', 'summa_usd'),
        }),
        ("Manba obyekti", {
            'fields': ('chiqim', 'xomashyo_harakat', '_manba_link'),
        }),
        ("Kim", {
            'fields': ('ishchi', 'foydalanuvchi', 'created_at'),
        }),
    )
    ordering = ('-sana', '-created_at')

    def has_add_permission(self, request):
        return False  # Faqat signal orqali yaratiladi

    def has_change_permission(self, request, obj=None):
        return False  # Immutable log

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'ishchi', 'foydalanuvchi',
            'chiqim__category',
            'xomashyo_harakat__xomashyo',
        )

    @admin.display(description="Tur")
    def _manba_badge(self, obj):
        if obj.manba == 'chiqim':
            return format_html(
                '<span style="background:#fef2f2;color:#dc2626;border:1px solid #fecaca;'
                'padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">Chiqim</span>'
            )
        return format_html(
            '<span style="background:#fef3c7;color:#b45309;border:1px solid #fcd34d;'
            'padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">Xomashyo</span>'
        )

    @admin.display(description="Summa (UZS)", ordering='summa_uzs')
    def _summa_uzs(self, obj):
        return format_html(
            '<span style="font-weight:800;color:#dc2626">{}</span>',
            _fmt(obj.summa_uzs)
        )

    @admin.display(description="Summa (USD)")
    def _summa_usd(self, obj):
        if obj.summa_usd:
            return format_html(
                '<span style="color:#1d4ed8;font-weight:700">${}</span>',
                f"{float(obj.summa_usd):,.2f}"
            )
        return "—"

    @admin.display(description="Manba obyekt")
    def _manba_link(self, obj):
        if obj.chiqim_id:
            try:
                url = reverse('admin:crm_chiqim_change', args=[obj.chiqim_id])
                return format_html('<a href="{}">Chiqim #{}</a>', url, obj.chiqim_id)
            except Exception:
                return f"Chiqim #{obj.chiqim_id}"
        if obj.xomashyo_harakat_id:
            try:
                url = reverse('admin:xomashyo_xomashyoharakat_change', args=[obj.xomashyo_harakat_id])
                return format_html('<a href="{}">Xomashyo #{}</a>', url, obj.xomashyo_harakat_id)
            except Exception:
                return f"Xomashyo #{obj.xomashyo_harakat_id}"
        return "—"