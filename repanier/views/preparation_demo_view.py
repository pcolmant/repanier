from io import BytesIO

from django.contrib.auth.decorators import permission_required
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook

from repanier.accounting_policy import AccountingPolicy
from repanier.preparation_demo import create_demo_preparation, reset_demo_preparation
from repanier.models.permanence import Permanence
from repanier.models.purchase import Purchase
from repanier.models.preparation import DepositReceipt, PreparationSyncEvent


def _staff_allowed(user):
    return user.is_authenticated and (
        getattr(user, "is_invoice_manager", False)
        or getattr(user, "is_repanier_staff", False)
        or user.is_superuser
    )


@require_POST
@csrf_protect
def demo_create(request):
    if not AccountingPolicy.use_mobile_preparation() or not _staff_allowed(request.user):
        raise Http404
    result = create_demo_preparation()
    return JsonResponse(
        {
            "permanence_id": result["permanence"].id,
            "token": result["token"],
            "is_demo": True,
        }
    )


@require_POST
@csrf_protect
def demo_reset(request, permanence_id):
    if not AccountingPolicy.use_mobile_preparation() or not _staff_allowed(request.user):
        raise Http404
    permanence = reset_demo_preparation(permanence_id)
    if permanence is None:
        raise Http404
    return JsonResponse({"reset": True, "permanence_id": permanence.id})


@require_GET
def demo_status(request, permanence_id):
    if not AccountingPolicy.use_mobile_preparation() or not _staff_allowed(request.user):
        raise Http404
    permanence = (
        Permanence.objects.filter(id=permanence_id, is_demo=True).first()
    )
    if permanence is None:
        raise Http404
    return JsonResponse(
        {
            "permanence_id": permanence.id,
            "is_demo": True,
            "purchases": Purchase.objects.filter(permanence=permanence).count(),
            "sync_events": PreparationSyncEvent.objects.filter(permanence=permanence).count(),
            "deposit_receipts": DepositReceipt.objects.filter(permanence=permanence).count(),
        }
    )


@require_POST
@csrf_protect
def demo_replay(request, permanence_id):
    if not AccountingPolicy.use_mobile_preparation() or not _staff_allowed(request.user):
        raise Http404
    permanence = (
        Permanence.objects.filter(id=permanence_id, is_demo=True).first()
    )
    if permanence is None:
        raise Http404
    reset_demo_preparation(permanence.id)
    return JsonResponse({"replayed": True, "permanence_id": permanence.id})


@require_GET
def demo_export(request, permanence_id):
    if not AccountingPolicy.use_mobile_preparation() or not _staff_allowed(request.user):
        raise Http404
    permanence = (
        Permanence.objects.filter(id=permanence_id, is_demo=True).first()
    )
    if permanence is None:
        raise Http404

    wb = Workbook()
    ws = wb.active
    ws.title = "TEST DATA"
    ws.append(["TEST DATA", "Do not use in real accounting"])
    ws.append(["Purchase", "Prepared", "Received", "Origin", "UUID"])
    for event in PreparationSyncEvent.objects.filter(permanence=permanence).order_by(
        "client_timestamp", "id"
    ):
        ws.append([
            event.purchase_id,
            "",
            "",
            event.operation,
            str(event.uuid),
        ])

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    from django.http import HttpResponse
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        'attachment; filename="TEST-data-permanence-{}.xlsx"'.format(permanence.id)
    )
    return response
