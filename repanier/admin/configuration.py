from django import forms
from django.conf import settings
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
from repanier.const import EMPTY_STRING
from repanier.models.configuration import Configuration
from repanier.widget.button_test_mail_config import ButtonTestMailConfigWidget


class ConfigurationDataForm(forms.ModelForm):
    home_site = forms.URLField(
        label=_("Home site"),
        required=False,
        widget=forms.URLInput(attrs={"style": "width:100% !important"}),
    )
    group_name = forms.CharField(
        label=_("Name of the group"),
        max_length=50,
        initial=settings.REPANIER_SETTINGS_GROUP_NAME,
    )
    email = forms.CharField(
        label=_("Email"), required=True, initial=settings.DEFAULT_FROM_EMAIL
    )
    send_test_mail_button = forms.CharField(
        # label=_("Test the email address"),
        label=EMPTY_STRING,
        widget=ButtonTestMailConfigWidget,
        required=False,
    )
    group_label_v2 = forms.CharField(
        label=_("Label to mention on the invoices of the group"),
        required=False,
        widget=forms.TextInput(attrs={"style": "width:100% !important"}),
    )

    def __init__(self, *args, **kwargs):
        super(ConfigurationDataForm, self).__init__(*args, **kwargs)
        self.fields["group_name"].widget.attrs["readonly"] = True
        self.fields["email"].widget.attrs["readonly"] = True

    # def clean(self):
    #     if any(self.errors):
    #         # Don't bother validating the formset unless each form is valid on its own
    #         return
    #     if not settings.REPANIER_SETTINGS_DEMO:
    #         new_email_host_password = self.cleaned_data["new_email_host_password"]
    #         if not new_email_host_password:
    #             self.instance.email_host_password = self.instance.previous_email_host_password
    #         else:
    #             self.instance.email_host_password = new_email_host_password

    class Meta:
        model = Configuration
        fields = "__all__"


class ConfigurationAdmin(admin.ModelAdmin):
    form = ConfigurationDataForm

    def has_delete_permission(self, request, obj=None):
        # Nobody even a superadmin
        return False

    def has_add_permission(self, request):
        # Nobody even a superadmin
        # There is only one configuration record created at application start
        return False

    def has_change_permission(self, request, obj=None):
        # Only a repanier_admin has this permission
        return request.user.is_repanier_admin

    def get_fieldsets(self, *args, **kwargs):
        fields = [
            ("group_name", "name"),
            "email",
            "send_test_mail_button",
            "bank_account",
            "max_week_wo_participation",
            ("membership_fee", "membership_fee_duration"),
            "display_anonymous_order_form",
            "display_who_is_who",
            "how_to_register_v2",
        ]
        fieldsets = [
            (
                None,
                {
                    "fields": fields,
                },
            ),
        ]
        fieldsets += [
            (
                _("Opening mails"),
                {
                    "classes": ("collapse",),
                    "fields": ("offer_customer_mail_v2",),
                },
            ),
        ]
        if settings.REPANIER_SETTINGS_CUSTOMER_MUST_CONFIRM_ORDER:
            fieldsets += [
                (
                    _("Ordering mails"),
                    {
                        "classes": ("collapse",),
                        "fields": (
                            "send_abstract_order_mail_to_customer",
                            "order_customer_mail_v2",
                            "cancel_order_customer_mail_v2",
                            "order_producer_mail_v2",
                            "send_order_mail_to_board",
                            "order_staff_mail_v2",
                        ),
                    },
                ),
            ]
        else:
            fieldsets += [
                (
                    _("Ordering mails"),
                    {
                        "classes": ("collapse",),
                        "fields": (
                            "send_abstract_order_mail_to_customer",
                            "order_customer_mail_v2",
                            "order_producer_mail_v2",
                            "send_order_mail_to_board",
                            "order_staff_mail_v2",
                        ),
                    },
                )
            ]
        if settings.REPANIER_SETTINGS_MANAGE_ACCOUNTING:
            fieldsets += [
                (
                    _("Invoicing mails"),
                    {
                        "classes": ("collapse",),
                        "fields": (
                            "send_invoice_mail_to_customer",
                            "invoice_customer_mail_v2",
                            "send_invoice_mail_to_producer",
                            "invoice_producer_mail_v2",
                        ),
                    },
                ),
            ]
        fields = [
            "home_site",
            "group_label_v2",
            ("currency", "vat_id"),
        ]
        fieldsets += [
            (
                _("Advanced options"),
                {
                    "classes": ("collapse",),
                    "fields": fields,
                },
            ),
        ]

        return fieldsets
