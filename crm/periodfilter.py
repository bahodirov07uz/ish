from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from datetime import timedelta
from django.utils import timezone

class Last15DaysFilter(admin.SimpleListFilter):
    title = _("Vaqt oralig'i")
    parameter_name = 'dynamic_date_range'

    def lookups(self, request, model_admin):
        return (
            ('15', _('Oxirgi 15 kun')),
        )

    def queryset(self, request, queryset):
        if not self.value():
            return queryset

        # Model ichidan vaqt maydonini qidiramiz
        model_fields = [f.name for f in queryset.model._meta.get_fields()]
        
        # Ustuvorlik bo'yicha maydon nomlari ro'yxati
        possible_fields = ['created_at', 'created', 'date_joined', 'sana', 'timestamp']
        
        target_field = None
        for field in possible_fields:
            if field in model_fields:
                target_field = field
                break
        
        if target_field:
            days = int(self.value())
            start_date = timezone.now() - timedelta(days=days)
            # Dinamik filtr: {field_name}__gte
            filter_kwargs = {f"{target_field}__gte": start_date}
            return queryset.filter(**filter_kwargs)
        
        return queryset