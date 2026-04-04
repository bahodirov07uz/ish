import requests
from decimal import Decimal

def get_usd_rate():
    """CBU dan USD kursini olish"""
    try:
        response = requests.get(
            'https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/',
            timeout=5
        )
        data = response.json()
        if data:
            return Decimal(str(data[0]['Rate']))
    except Exception:
        pass
    return Decimal('0')