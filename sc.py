import os
import json
import django
from django.utils.timezone import now

# Django sozlamalarini yuklash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Loyiha nomini o'zgartiring
django.setup()

from django.db import transaction
import re

from crm.models import Chiqim,ChiqimItem

from xomashyo.models import XomashyoHarakat
from crm.models import Ish

def run():
    print("bosjlandi")
    
    with transaction.atomic():
        yangilangan_count  = 0
        ish =  Ish.objects.filter(status='yangi')
        ish.update(status='yopilgan')
        ish.save
            
        
        
        
        
if __name__ == "__main__":
    run()