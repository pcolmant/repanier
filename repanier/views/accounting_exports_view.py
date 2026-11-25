from django import forms
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

from repanier.accounting_policy import AccountingPolicy
from repanier.const import BankMovement, SaleStatus
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.group import Group
from repanier.models.offeritem import OfferItem
from repanier.xlsx.xlsx_accounting_exports import (
    AccountingExportFilters,
    export_closing_producer_response,
    export_member_accounts_response,
    export_preparation_trace,
    export_purchase_lines,
    _http_response,
)


class AccountingExportFilterForm(forms.Form):
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)
    permanence = forms.ModelChoiceField(
        queryset=Permanence.objects.filter(is_demo=False),
        required=False,
    )
    offer = forms.ModelChoiceField(
        queryset=OfferItem.objects.filter(permanence__is_demo=False),
        required=False,
        help_text=_("Applies to purchase-line exports only."),
    )
    producer = forms.ModelChoiceField(
        queryset=Producer.objects.filter(is_active=True),
        required=False,
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(is_active=True),
        required=False,
    )
    customer = forms.CharField(required=False)
    status = forms.ChoiceField(
        choices=(("", _("All")),) + tuple(SaleStatus.choices),
        required=False,
    )
    operation_status = forms.ChoiceField(
        choices=(("", _("All")),) + tuple(BankMovement.choices),
        required=False,
    )


@staff_member_required
def accounting_exports(request):
    user = request.user
    if not getattr(user, "is_invoice_manager", False) and not user.is_superuser:
        raise Http404

    form = AccountingExportFilterForm(request.GET or None)
    filters = AccountingExportFilters(
        {
            "date_from": request.GET.get("date_from"),
            "date_to": request.GET.get("date_to"),
            "permanence": request.GET.get("permanence"),
            "offer": request.GET.get("offer"),
            "producer": request.GET.get("producer"),
            "group": request.GET.get("group"),
            "customer": request.GET.get("customer"),
            "status": request.GET.get("status"),
            "operation_status": request.GET.get("operation_status"),
        }
    )

    producer_preview = []
    member_preview = []
    if form.is_valid():
        producer_preview = list(
            filters.producer_closures()[:20]
            if AccountingPolicy.manage_accounting()
            else []
        )
        member_preview = list(
            filters.member_accounts()[:20]
            if AccountingPolicy.manage_member_balances()
            else []
        )

    if request.GET.get("download") == "producer":
        response = export_closing_producer_response(filters)
        if response is None:
            raise Http404
        return response
    if request.GET.get("download") == "member":
        response = export_member_accounts_response(filters)
        if response is None:
            raise Http404
        return response
    if request.GET.get("download") == "preparation_trace":
        wb = export_preparation_trace(filters)
        return _http_response(wb, "preparation-accounting-trace")
    if request.GET.get("download") == "purchase_lines":
        wb = export_purchase_lines(filters)
        return _http_response(wb, "purchase-lines")

    if not AccountingPolicy.use_groups():
        form.fields["group"].disabled = True

    return render(
        request,
        "repanier/admin/accounting_exports.html",
        {
            "form": form,
            "producer_preview": producer_preview,
            "member_preview": member_preview,
            "REPANIER_MANAGE_MEMBER_BALANCES": AccountingPolicy.manage_member_balances(),
        },
    )
