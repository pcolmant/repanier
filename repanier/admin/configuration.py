from django import forms
from django.conf import settings
from django.contrib.admin import ModelAdmin
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
        label=EMPTY_STRING,
        widget=ButtonTestMailConfigWidget,
        required=False,
    )
    certification = forms.CharField(
        label=_("Certification to mention on the invoices"),
        required=False,
        widget=forms.TextInput(attrs={"style": "width:100% !important"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group_name"].widget.attrs["readonly"] = True
        self.fields["email"].widget.attrs["readonly"] = True

    class Meta:
        model = Configuration
        fields = "__all__"


class ConfigurationAdmin(ModelAdmin):
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
            ("group_name", "bank_account"),
            "email",
            "send_test_mail_button",
            "max_week_wo_participation",
            ("membership_fee", "membership_fee_duration"),
            "display_anonymous_order_form",
            "display_who_is_who",
            "how_to_create_an_account",
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
                    "fields": ("mail_offer_customer",),
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
                            "mail_order_customer",
                            "mail_cancel_order_customer",
                            "mail_order_producer",
                            "send_order_mail_to_board",
                            "mail_order_staff",
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
                            "mail_order_customer",
                            "mail_order_producer",
                            "send_order_mail_to_board",
                            "mail_order_staff",
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
                            "mail_invoice_customer",
                            "send_invoice_mail_to_producer",
                            "mail_invoice_producer",
                        ),
                    },
                ),
            ]

        fields = [
            "home_site",
            "certification",
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
