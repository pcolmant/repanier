from django import forms
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from easy_select2 import apply_select2
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats.base_formats import CSV, XLSX, XLS

from repanier.admin.admin_filter import BankAccountFilterByStatus
from repanier.const import *
from repanier.fields.RepanierMoneyField import FormMoneyField
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import ProducerInvoice, CustomerInvoice
from repanier.models.producer import Producer
from repanier.xlsx.widget import (
    IdWidget,
    TwoMoneysWidget,
    ProducerNameWidget,
    CustomerNameWidget,
    DateWidgetExcel,
)


class BankAccountResource(resources.ModelResource):
    id = fields.Field(attribute="id", widget=IdWidget(), readonly=True)
    permanence = fields.Field(attribute="permanence", readonly=True)
    operation_date = fields.Field(attribute="operation_date", widget=DateWidgetExcel())
    operation_status = fields.Field(attribute="operation_status", readonly=True)
    producer_name = fields.Field(
        attribute="producer",
        widget=ProducerNameWidget(Producer, field="short_name"),
    )
    customer_name = fields.Field(
        attribute="customer",
        widget=CustomerNameWidget(Customer, field="short_name"),
    )
    bank_amount_in = fields.Field(attribute="bank_amount_in", widget=TwoMoneysWidget())
    bank_amount_out = fields.Field(
        attribute="bank_amount_out", widget=TwoMoneysWidget()
    )
    customer_invoice = fields.Field(
        attribute="customer_invoice__date_balance",
        widget=DateWidgetExcel(),
        readonly=True,
    )
    producer_invoice = fields.Field(
        attribute="producer_invoice__date_balance",
        widget=DateWidgetExcel(),
        readonly=True,
    )

    def before_save_instance(self, instance, using_transactions, dry_run):
        """
        Override to add additional logic.
        """
        if instance.id is None:
            if instance.producer is None and instance.customer is None:
                if (
                    instance.bank_amount_out is not None
                    and instance.bank_amount_out != DECIMAL_ZERO
                ):
                    only_one_target = (
                        ProducerInvoice.objects.filter(
                            status=PERMANENCE_SEND,
                            total_price_with_tax=instance.bank_amount_out,
                        )
                        .order_by("?")
                        .count()
                    )
                    if only_one_target == 1:
                        instance.producer = (
                            ProducerInvoice.objects.filter(
                                status=PERMANENCE_SEND,
                                total_price_with_tax=instance.bank_amount_out,
                            )
                            .order_by("?")
                            .first()
                            .producer
                        )
                elif (
                    instance.bank_amount_in is not None
                    and instance.bank_amount_in != DECIMAL_ZERO
                ):
                    only_one_target = (
                        CustomerInvoice.objects.filter(
                            status=PERMANENCE_SEND,
                            total_price_with_tax=instance.bank_amount_in,
                        )
                        .order_by("?")
                        .count()
                    )
                    if only_one_target == 1:
                        instance.customer = (
                            CustomerInvoice.objects.filter(
                                status=PERMANENCE_SEND,
                                total_price_with_tax=instance.bank_amount_in,
                            )
                            .order_by("?")
                            .first()
                            .customer
                        )
                if instance.producer is None and instance.customer is None:
                    raise ValueError(_("No producer nor customer found."))
            if instance.bank_amount_out is None:
                instance.bank_amount_out = DECIMAL_ZERO
            if instance.bank_amount_in is None:
                instance.bank_amount_in = DECIMAL_ZERO
            if instance.producer is not None and instance.customer is not None:
                raise ValueError(_("Only a customer or a producer may be entered."))
            if instance.producer is not None:
                if BankAccount.objects.filter(
                    producer=instance.producer,
                    bank_amount_in=instance.bank_amount_in,
                    bank_amount_out=instance.bank_amount_out,
                    operation_date=instance.operation_date,
                ).exists():
                    raise ValueError(_("This movement already exists."))
                if BankAccount.objects.filter(
                    producer=instance.producer,
                    bank_amount_in=instance.bank_amount_in,
                    bank_amount_out=instance.bank_amount_out,
                    operation_comment=instance.operation_comment,
                ).exists():
                    raise ValueError(_("This movement already exists."))
            if instance.customer is not None:
                if BankAccount.objects.filter(
                    customer=instance.customer,
                    bank_amount_in=instance.bank_amount_in,
                    bank_amount_out=instance.bank_amount_out,
                    operation_date=instance.operation_date,
                ).exists():
                    raise ValueError(_("This movement already exists."))
                if BankAccount.objects.filter(
                    customer=instance.customer,
                    bank_amount_in=instance.bank_amount_in,
                    bank_amount_out=instance.bank_amount_out,
                    operation_comment=instance.operation_comment,
                ).exists():
                    raise ValueError(_("This movement already exists."))

    def skip_row(self, instance, original):
        if instance.id is not None:
            # The import may not be used to update bank movements.
            return True
        super().skip_row(instance, original)

    class Meta:
        model = BankAccount
        fields = (
            "id",
            "permanence",
            "operation_date",
            "operation_status",
            "producer_name",
            "customer_name",
            "bank_amount_in",
            "bank_amount_out",
            "operation_comment",
            "customer_invoice",
            "producer_invoice",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        use_transactions = False


class CustomerModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Important "if obj.bank_account" and not "if obj.bank_account is not None"
        # to handle the case of empty string
        bank_account1 = "-{}".format(
            obj.bank_account1 if obj.bank_account1 else EMPTY_STRING
        )
        bank_account2 = "-{}".format(
            obj.bank_account2 if obj.bank_account2 else EMPTY_STRING
        )
        return "{}{}{}".format(obj.short_name, bank_account1, bank_account2)


class ProducerModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Important "if obj.bank_account" and not "if obj.bank_account is not None"
        bank_account = "-{}".format(
            obj.bank_account if obj.bank_account else EMPTY_STRING
        )
        return "{}{}".format(obj.short_name, bank_account)


class BankAccountDataForm(forms.ModelForm):
    customer = CustomerModelChoiceField(
        queryset=Customer.objects.filter(is_active=True),
        label=_("Customer"),
        required=False,
        widget=apply_select2(forms.Select),
    )
    producer = ProducerModelChoiceField(
        queryset=Producer.objects.filter(
            represent_this_buyinggroup=False, is_active=True
        ),
        label=_("Producer"),
        required=False,
        widget=apply_select2(forms.Select),
    )

    bank_amount_in = FormMoneyField(
        label=_("Cash in"),
        help_text=_("Payment on the account"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )
    bank_amount_out = FormMoneyField(
        label=_("Cash out"),
        help_text=_("Payment from the account"),
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=REPANIER_MONEY_ZERO,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        bank_account = self.instance
        if bank_account.id is not None:
            self.fields["bank_amount_in"].initial = bank_account.bank_amount_in
            self.fields["bank_amount_out"].initial = bank_account.bank_amount_out
            self.fields["customer"].widget.attrs["readonly"] = True
            self.fields["customer"].disabled = True
            self.fields["producer"].widget.attrs["readonly"] = True
            self.fields["producer"].disabled = True

            if bank_account.customer is None:
                self.fields["customer"].choices = [("", _("---------"))]
            else:
                self.fields["customer"].empty_label = None
                self.fields["customer"].queryset = Customer.objects.filter(
                    id=bank_account.customer_id
                )
            if bank_account.producer is None:
                self.fields["producer"].choices = [("", _("---------"))]
            else:
                self.fields["producer"].empty_label = None
                self.fields["producer"].queryset = Producer.objects.filter(
                    id=bank_account.producer_id
                )

            if (
                bank_account.customer_invoice is not None
                or bank_account.producer_invoice is not None
            ) or (bank_account.customer is None and bank_account.producer is None):
                self.fields["operation_date"].widget.attrs["readonly"] = True
                self.fields["operation_date"].disabled = True
                self.fields["bank_amount_in"].widget.attrs["readonly"] = True
                self.fields["bank_amount_in"].disabled = True
                self.fields["bank_amount_out"].widget.attrs["readonly"] = True
                self.fields["bank_amount_out"].disabled = True
                if bank_account.customer is None and bank_account.producer is None:
                    self.fields["operation_comment"].widget.attrs["readonly"] = True
                    self.fields["operation_comment"].disabled = True
        else:
            self.fields["producer"].queryset = Producer.objects.filter(
                represent_this_buyinggroup=False, is_active=True
            )
            self.fields["customer"].queryset = Customer.objects.filter(is_active=True)

    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        customer = self.cleaned_data.get("customer")
        producer = self.cleaned_data.get("producer")
        initial_id = self.instance.id
        initial_customer = self.instance.customer
        initial_producer = self.instance.producer
        if customer is None and producer is None:
            if initial_id is not None:
                if initial_customer is None and initial_producer is None:
                    raise forms.ValidationError(_("You may not update a balance."))
                else:
                    self.add_error(
                        "customer", _("Either a customer or a producer must be set.")
                    )
                    self.add_error(
                        "producer", _("Either a customer or a producer must be set.")
                    )
            else:
                bank_account = (
                    BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL)
                    .order_by("?")
                    .first()
                )
                if bank_account:
                    # You may only insert the first latest bank total at initialisation of the website
                    self.add_error(
                        "customer", _("Either a customer or a producer must be set.")
                    )
                    self.add_error(
                        "producer", _("Either a customer or a producer must be set.")
                    )
        else:
            if (
                self.instance.customer_invoice is not None
                or self.instance.producer_invoice is not None
            ):
                raise forms.ValidationError(
                    _("You may not update a bank operation linked to an invoice.")
                )
        if customer is not None and producer is not None:
            self.add_error(
                "customer", _("Only one customer or one producer must be given.")
            )
            self.add_error(
                "producer", _("Only one customer or one producer must be given.")
            )
        latest_total = (
            BankAccount.objects.filter(operation_status=BANK_LATEST_TOTAL)
            .order_by("?")
            .first()
        )
        if latest_total is not None:
            operation_date = self.cleaned_data.get("operation_date")
            if operation_date < latest_total.operation_date:
                self.add_error(
                    "operation_date",
                    _(
                        "The operation date must be greater or equal to the latest total operation date."
                    ),
                )

    class Meta:
        model = BankAccount
        fields = "__all__"


class BankAccountAdmin(ImportExportMixin, admin.ModelAdmin):
    form = BankAccountDataForm
    resource_class = BankAccountResource
    fields = (
        "operation_date",
        ("producer", "customer"),
        "operation_comment",
        "bank_amount_in",
        "bank_amount_out",
        ("customer_invoice", "producer_invoice"),
        "is_updated_on",
    )
    list_per_page = 16
    list_max_show_all = 16
    list_display = [
        "operation_date",
        "get_producer",
        "get_customer",
        "get_bank_amount_in",
        "get_bank_amount_out",
        "operation_comment",
    ]
    date_hierarchy = "operation_date"
    list_filter = (BankAccountFilterByStatus,)
    ordering = ("-operation_date", "-id")
    search_fields = (
        "producer__short_name",
        "customer__short_name",
        "operation_comment",
    )
    actions = []

    def has_delete_permission(self, request, bank_account=None):
        return False

    def has_add_permission(self, request):
        user = request.user
        if user.is_invoice_manager:
            return True
        return False

    def has_change_permission(self, request, bank_account=None):
        return self.has_add_permission(request)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ["is_updated_on", "customer_invoice", "producer_invoice"]
        return readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        if "delete_selected" in actions:
            del actions["delete_selected"]
        if not actions:
            try:
                self.list_display.remove("action_checkbox")
            except ValueError:
                pass
            except AttributeError:
                pass
        return actions

    def get_import_formats(self):
        """
        Returns available import formats.
        """
        return [f for f in (XLSX, XLS, CSV) if f().can_import()]

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in (XLSX, CSV) if f().can_export()]
