from django.utils.translation import ugettext_lazy as _
from import_export import resources, fields
from import_export.widgets import CharWidget

from repanier_v2.const import DECIMAL_ONE
from repanier_v2.models.producer import Producer
from repanier_v2.xlsx.widget import (
    IdWidget,
    TwoDecimalsWidget,
    DecimalBooleanWidget,
)


class ProducerResource(resources.ModelResource):

    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    phone1 = fields.Field(attribute="phone1", widget=CharWidget(), readonly=False)
    purchase_tariff_margin = fields.Field(
        attribute="purchase_tariff_margin",
        default=DECIMAL_ONE,
        widget=TwoDecimalsWidget(),
        readonly=False,
    )
    customer_tariff_margin = fields.Field(
        attribute="customer_tariff_margin",
        default=DECIMAL_ONE,
        widget=TwoDecimalsWidget(),
        readonly=False,
    )
    invoice_by_basket = fields.Field(
        attribute="invoice_by_basket",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    sort_products_by_reference = fields.Field(
        attribute="sort_products_by_reference",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=False,
    )
    is_default = fields.Field(
        attribute="is_default",
        default=False,
        widget=DecimalBooleanWidget(),
        readonly=True,
    )
    is_active = fields.Field(
        attribute="is_active", widget=DecimalBooleanWidget(), readonly=True
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        producer_qs = Producer.objects.filter(short_name=instance.short_name).order_by(
            "?"
        )
        if instance.id is not None:
            producer_qs = producer_qs.exclude(id=instance.id)
        if producer_qs.exists():
            raise ValueError(
                _("The short_name {} is already used by another producer.").format(
                    instance.short_name
                )
            )

    class Meta:
        model = Producer
        fields = (
            "id",
            "short_name",
            "long_name",
            "email",
            "language",
            "phone1",
            "invoice_by_basket",
            "sort_products_by_reference",
            "producer_tariff_is_wo_tax",
            "purchase_tariff_margin",
            "customer_tariff_margin",
            "bank_account",
            "is_default",
            "is_active",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False
