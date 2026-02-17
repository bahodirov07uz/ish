from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from crm.models import Ishchi, IshchiCategory,Product,ProductVariant,Category,Ish,Chiqim,Kirim,ChiqimTuri,Sotuv,Xaridor,SotuvItem
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
            'type',
            'izoh'
            
        )
        import_id_fields = ('product', 'rang', 'razmer')
        skip_unchanged = True
        report_skipped = True

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

class SotuvResource(resources.ModelResource):
    xaridor_ism = fields.Field(
        column_name="xaridor",
        attribute="xaridor",
        widget=CreateIfNotExistWidget(Xaridor,"ism")
    )
    
    class Meta:
        model = Xaridor
        fields = ("id","ism","telefon","manzil")
        export_order = ("id","ism","telefon","manzil" )
        
        
from decimal import Decimal

class SotuvItemResource(resources.ModelResource):
    # Foreign key'larni ID orqali emas, aniq maydonlar orqali bog'lash uchun fields
    sotuv = fields.Field(
        column_name='sotuv_id',
        attribute='sotuv',
        widget=ForeignKeyWidget(Sotuv, 'id')
    )
    mahsulot = fields.Field(
        column_name='mahsulot_nomi',
        attribute='mahsulot',
        widget=ForeignKeyWidget(Product, 'nomi') # Mahsulot nomi orqali qidirish
    )
    # Variantni tanlashda (mahsulot, rang, razmer) birikmasi muhim
    # Lekin importda oson bo'lishi uchun variant_id ishlatish tavsiya etiladi
    variant = fields.Field(
        column_name='variant_id',
        attribute='variant',
        widget=ForeignKeyWidget(ProductVariant, 'id')
    )

    class Meta:
        model = SotuvItem
        fields = ('id', 'variant', 'sotuv', 'mahsulot','variant__rang', 'miqdor', 'narx', 'izoh')
        export_order = fields
        # Import qilinganda modeldagi save() metodini ishlatishga majburlash
        force_init_instance = True 

    def before_import_row(self, row, **kwargs):
        """
        Importdan oldin ma'lumotlarni tekshirish yoki o'zgartirish
        """
        # Masalan, narx decimal bo'lishini ta'minlash
        if 'narx' in row and row['narx']:
            row['narx'] = Decimal(str(row['narx']))
        
    def save_instance(self, instance, is_create, row, **kwargs):
        """
        Modelning save() metodini chaqirish orqali stock va summalarni 
        avtomatik yangilanishini ta'minlaydi.
        """
        # Modelda yozilgan ValidationError yoki ValueError'larni tutib qolish
        try:
            super().save_instance(instance, is_create, row, **kwargs)
        except ValueError as e:
            # Xatolik bo'lsa import jarayonini to'xtatadi va xabarni ko'rsatadi
            raise Exception(f"Qatorda xatolik: {str(e)}")