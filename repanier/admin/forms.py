from django import forms
from django.contrib.admin.widgets import AdminDateWidget
from django.forms.formsets import formset_factory
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.widgets import TextEditorWidget
from recurrence.forms import RecurrenceField

from repanier.const import REPANIER_MONEY_ZERO, EMPTY_STRING
from repanier.fields.RepanierMoneyField import FormRepanierMoneyField
from repanier.models.producer import Producer
from repanier.tools import get_repanier_template_name


class OpenAndSendOfferForm(forms.Form):
    template_offer_customer_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget, required=False
    )
    template_cancel_order_customer_mail = forms.CharField(
        label=_("If customers must confirm orderds, cancelled order customer mail"),
        widget=TextEditorWidget,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class CloseAndSendOrderForm(forms.Form):
    template_order_customer_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget, required=False
    )
    template_order_producer_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget, required=False
    )
    template_order_staff_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget, required=False
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class GeneratePermanenceForm(forms.Form):
    # repeat_counter = forms.IntegerField(label=_("Number of permanence(s)"), min_value=0, max_value=54)
    # repeat_step = forms.IntegerField(label=_("Number of week(s) between two permanences"), min_value=0, max_value=12)
    recurrences = RecurrenceField()

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class PermanenceInvoicedForm(forms.Form):
    payment_date = forms.DateField(
        label=_("Payment date"), required=True, widget=AdminDateWidget()
    )

    def __init__(self, *args, **kwargs):
        self.payment_date = kwargs.pop("payment_date", None)
        super().__init__(*args, **kwargs)

        self.fields["payment_date"].initial = self.payment_date

    class Media:
        # Needed for AdminDateWidget
        js = (
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/jquery.init.js",
            "admin/js/core.js",
        )
        css = {"all": ("admin/css/forms.css",)}


class ImportStockForm(forms.Form):
    template = get_repanier_template_name("admin/import_stock.html")
    file_to_import = forms.FileField(label=_("File to import"), allow_empty_file=False)


class ImportPurchasesForm(forms.Form):
    template = get_repanier_template_name("admin/import_purchases.html")
    file_to_import = forms.FileField(label=_("File to import"), allow_empty_file=False)


class ImportInvoiceForm(forms.Form):
    template = get_repanier_template_name("admin/import_invoice.html")
    file_to_import = forms.FileField(label=_("File to import"), allow_empty_file=False)
    # Important : Here, the length of invoice_reference must be the same as of permanence.short_name
    invoice_reference = forms.CharField(
        label=_("Invoice reference"), max_length=50, required=False
    )
    producer = forms.ModelChoiceField(
        label=_("Producer"),
        queryset=Producer.objects.filter(is_active=True).all(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["invoice_reference"].widget.attrs["style"] = "width:450px"


class ProducerInvoicedForm(forms.Form):
    selected = forms.BooleanField(required=False)
    id = forms.IntegerField(label=EMPTY_STRING)
    short_profile_name = forms.CharField(
        label=_("Short name"), max_length=25, required=False
    )
    calculated_invoiced_balance = FormRepanierMoneyField(
        label=_("Amount due to the producer as calculated by Repanier"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    to_be_invoiced_balance = FormRepanierMoneyField(
        label=_("Amount claimed by the producer"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    invoice_reference = forms.CharField(
        label=_("Invoice reference"), max_length=100, required=False
    )
    producer_price_are_wo_vat = forms.BooleanField(required=False)
    represent_this_buyinggroup = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["id"].widget.attrs["readonly"] = True
        self.fields["to_be_invoiced_balance"].widget.attrs["style"] = "width:100px"
        self.fields["invoice_reference"].widget.attrs["style"] = "width:250px"
        self.fields["calculated_invoiced_balance"].widget.attrs["readonly"] = True
        # self.fields["calculated_invoiced_balance"].widget.attrs['style'] = "width:100px"


ProducerInvoicedFormSet = formset_factory(ProducerInvoicedForm, extra=0)
