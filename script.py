from crm.models import Ish

ishlar = Ish.objects.filter(mahsulot__nomi='LR-TAPICH')

print(ishlar)