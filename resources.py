from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from crm.models import Ishchi, IshchiCategory,Product,ProductVariant,Category
from xomashyo.models import Xomashyo, XomashyoCategory, YetkazibBeruvchi


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
        )


class XomashyoResource(resources.ModelResource):
    category = fields.Field(
        column_name='category',
        attribute='category',
        widget=ForeignKeyWidget(XomashyoCategory, 'name')
    )

    mahsulot = fields.Field(
        column_name='mahsulot',
        attribute='mahsulot',
        widget=ForeignKeyWidget(Product, 'nomi'),
    )

    yetkazib_beruvchi = fields.Field(
        column_name='yetkazib_beruvchi',
        attribute='yetkazib_beruvchi',
        widget=ForeignKeyWidget(YetkazibBeruvchi, 'nomi'),
    )

    class Meta:
        model = Xomashyo
        fields = (
            'id',
            'nomi',
            'category',
            'mahsulot',
            'rang',
            'miqdori',
            'olchov_birligi',
            'minimal_miqdor',
            'narxi',
            'yetkazib_beruvchi',
            'holati',
            'qr_code',
        )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Import vaqtida clean() ni majburan chaqiramiz
        """
        instance.full_clean()
