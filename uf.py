import os
import json
import django
from django.utils.timezone import now
from django.db.models import Sum
# Django sozlamalarini yuklash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Loyiha nomini o'zgartiring
django.setup()

from django.db import transaction
import re

from crm.models import Chiqim,ChiqimItem

from xomashyo.models import XomashyoHarakat
from crm.models import Ish,Product

ishlar = Ish.objects.filter(status='yangi')

ishlar.update(status='yopilgan')