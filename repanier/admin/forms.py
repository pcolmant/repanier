from django import forms
from django.forms.formsets import formset_factory
from django.utils.translation import ugettext_lazy as _
from djangocms_text_ckeditor.widgets import TextEditorWidget
from recurrence.forms import RecurrenceField

from repanier.models.producer import Producer
from repanier.const import REPANIER_MONEY_ZERO
from repanier.fields.RepanierMoneyField import FormMoneyField


class OpenAndSendOfferForm(forms.Form):
    template_offer_customer_mail = forms.CharField(label=_("Email content"), widget=TextEditorWidget,
                                                   required=False)
    template_cancel_order_customer_mail = forms.CharField(
        label=_("If customers must confirm orderds, cancelled order customer mail"),
        widget=TextEditorWidget,
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(OpenAndSendOfferForm, self).__init__(*args, **kwargs)


class CloseAndSendOrderForm(forms.Form):
    template_order_customer_mail = forms.CharField(label=_("Email content"), widget=TextEditorWidget,
                                                   required=False)
    template_order_producer_mail = forms.CharField(label=_("Email content"), widget=TextEditorWidget,
                                                   required=False)
    template_order_staff_mail = forms.CharField(label=_("Email content"), widget=TextEditorWidget, required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(CloseAndSendOrderForm, self).__init__(*args, **kwargs)


class GeneratePermanenceForm(forms.Form):
    # repeat_counter = forms.IntegerField(label=_("Number of permanence(s)"), min_value=0, max_value=54)
    # repeat_step = forms.IntegerField(label=_("Number of week(s) between two permanences"), min_value=0, max_value=12)
    recurrences = RecurrenceField()

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(GeneratePermanenceForm, self).__init__(*args, **kwargs)


class InvoiceOrderForm(forms.Form):
    template_invoice_customer_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget,
                                                     required=False)
    template_invoice_producer_mail = forms.CharField(
        label=_("Email content"), widget=TextEditorWidget,
                                                     required=False)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(InvoiceOrderForm, self).__init__(*args, **kwargs)


class PermanenceInvoicedForm(forms.Form):
    payment_date = forms.DateField(label=_("Payment date"), required=True) #, widget=AdminDateWidget())

    def __init__(self, *args, **kwargs):
        self.payment_date = kwargs.pop('payment_date', None)
        super(PermanenceInvoicedForm, self).__init__(*args, **kwargs)

        self.fields['payment_date'].initial = self.payment_date


class ImportXlsxForm(forms.Form):
    template = 'repanier/import_xlsx.html'
    file_to_import = forms.FileField(label=_('File to import'), allow_empty_file=False)


class ImportInvoiceForm(ImportXlsxForm):
    template = 'repanier/import_invoice_xlsx.html'
    # Important : The length of invoice_reference must be the same as of permanence.short_name
    invoice_reference = forms.CharField(label=_("Invoice reference"), max_length=50, required=False)
    producer = forms.ModelChoiceField(label=_('Producer'), queryset=Producer.objects.filter(is_active=True).all(), required=False)

    def __init__(self, *args, **kwargs):
        super(ImportInvoiceForm, self).__init__(*args, **kwargs)
        self.fields["invoice_reference"].widget.attrs['style'] = "width:450px !important"


class ProducerInvoicedForm(forms.Form):
    selected = forms.BooleanField(required=False)
    short_profile_name = forms.CharField(label=_("Short name"), max_length=25, required=False)
    calculated_invoiced_balance = FormMoneyField(
        label=_("Calculated balance to be invoiced"), max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO)
    to_be_invoiced_balance = FormMoneyField(
        label=_("Amount claimed by the producer"), max_digits=8, decimal_places=2, required=False, initial=REPANIER_MONEY_ZERO)
    invoice_reference = forms.CharField(label=_("Invoice reference"), max_length=100, required=False)

    def __init__(self, *args, **kwargs):
        super(ProducerInvoicedForm, self).__init__(*args, **kwargs)
        self.fields["to_be_invoiced_balance"].widget.attrs['style'] = "width:100px !important"
        self.fields["invoice_reference"].widget.attrs['style'] = "width:250px !important"
        self.fields["calculated_invoiced_balance"].widget.attrs['readonly'] = True
        # self.fields["calculated_invoiced_balance"].widget.attrs['style'] = "width:100px"


ProducerInvoicedFormSet = formset_factory(ProducerInvoicedForm, extra=0)
