from django.contrib import admin
from .models import Byudjet

@admin.register(Byudjet)
class ByudjetAdmin(admin.ModelAdmin):
    list_display  = ('nomi','davr_boshi',)