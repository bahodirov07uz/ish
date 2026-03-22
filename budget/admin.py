from django.contrib import admin
from .models import Byudjet,Tranzaksiya

@admin.register(Byudjet)
class ByudjetAdmin(admin.ModelAdmin):
    list_display  = ('nomi','davr_boshi',)
    
@admin.register(Tranzaksiya)
class TranzaksiyaAdmin(admin.ModelAdmin):
    list_display = ('manba','summa_usd','summa_uzs','kategoriya','sana')