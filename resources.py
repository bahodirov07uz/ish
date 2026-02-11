from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from crm.models import Ishchi, IshchiCategory,Product,ProductVariant,Category,Ish,Chiqim,Kirim,ChiqimTuri,Feature
from xomashyo.models import Xomashyo, XomashyoCategory, YetkazibBeruvchi,XomashyoHarakat,XomashyoVariant
from django.conf import settings

class CreateIfNotExistWidget(ForeignKeyWidget):
    def clean(self, value, row=None, **kwargs):
        if not value:
            return None
        # get_or_create ishlatilganda, agar obyekt bo'lmasa 'field' nomi bilan yaratiladi
        obj, created = self.model.objects.get_or_create(**{self.field: value})
        return obj
    
class IshchiResource(resources.ModelResource):
    turi = fields.Field(
        column_name='turi',
        attribute='turi',
        widget=ForeignKeyWidget(IshchiCategory, 'nomi')
    )

    class Meta:
        model = Ishchi
        fields = (
            'id',
            'ism',
            'familiya',
            'telefon',
            'maosh',
            'turi',
            'is_active',
            'is_oylik_open',
            'yangi_oylik',
        )
        export_order = fields

class ProductResource(resources.ModelResource):
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyWidget(Category, 'name')
    )

    class Meta:
        model = Product
        fields = (
            'id',
            'nomi',
            'category',
            'status',
            'narxi',
            'avg_profit',
            'narx_kosib',
            'narx_zakatovka',
            'narx_kroy',
            'narx_pardoz',
            'teri_sarfi',
            'astar_sarfi',
        )

class ProductVariantResource(resources.ModelResource):
    product = fields.Field(
        column_name='product',
        attribute='product',
        widget=ForeignKeyWidget(Product, 'nomi')
    )

    class Meta:
        model = ProductVariant
        fields = (
            'id',
            'product',
            'rang',
            'razmer',
            'stock',
            'price',
            'izoh'
            
        )

class XomashyoResource(resources.ModelResource):
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=CreateIfNotExistWidget(XomashyoCategory, 'name')
    )

    mahsulot = fields.Field(
        column_name='mahsulot',
        attribute='mahsulot',
        widget=ForeignKeyWidget(Product, 'nomi'),
    )

    yetkazib_beruvchi = fields.Field(
        column_name='yetkazib_beruvchi',
        attribute='yetkazib_beruvchi',
        widget=CreateIfNotExistWidget(YetkazibBeruvchi, 'nomi'),
    )

    class Meta:
        model = Xomashyo
        fields = (
            'id', 'nomi', 'category', 'mahsulot', 'rang', 'miqdori', 
            'olchov_birligi', 'minimal_miqdor', 'narxi', 
            'yetkazib_beruvchi', 'holati', 'qr_code'
        )

    def before_save_instance(self, instance, *args, **kwargs):
        """
        *args qo'shish orqali barcha tartib bilan kelayotgan argumentlarni 
        (dry_run, using_transactions va h.k.) qabul qilib olamiz.
        """
        instance.full_clean() 
        
class IshResource(resources.ModelResource):
    
    ishchi = fields.Field(
        column_name="ishchi",
        attribute="ishchi",
        widget=ForeignKeyWidget(Ishchi,"ism")
    )
    product = fields.Field(
        column_name="mahsulot",
        attribute="mahsulot",
        widget=ForeignKeyWidget(Product,"nomi")
    )
    
    class Meta:
        model = Ish
        fields = (
            "id","mahsulot","ishchi","soni","sana","narxi","status"
        )

class XomashyoHarakatResource(resources.ModelResource):
    xomashyo = fields.Field(
        column_name="xomashyo",
        attribute="xomashyo",
        widget=ForeignKeyWidget(Xomashyo,"nomi")
    )
    
    xomashyo_variant = fields.Field(
        column_name="xomashyo_variant",
        attribute="xomashyo_variant",
        widget=ForeignKeyWidget(XomashyoVariant,"xomashyo")
    )
    
    foydalanuvchi = fields.Field(
        column_name="foydalanuvchi",
        attribute="foydalanuvchi",
        widget=ForeignKeyWidget(settings.AUTH_USER_MODEL,"username")
    )
    
    class Meta:
        model = XomashyoHarakat
        field = (
            "id","xomashyo","xomashyovariant","harakat_turi","miqdori","sana","izoh","foydalanuvchi"
        )

class ChiqimResource(resources.ModelResource):
    category_name = fields.Field(
        column_name="Kategoriya",
        attribute="category",
        widget=ForeignKeyWidget(ChiqimTuri, "name")
    )

    class Meta:
        model = Chiqim
        fields = ("id", "created", "name", "category_name", "price")
        export_order = ("id", "created", "name", "category_name", "price")
