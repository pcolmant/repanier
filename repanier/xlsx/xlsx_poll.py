from io import BytesIO
from django.db import models
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_poll_xlsx(poll):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _("Results")[:31]

    # Styles (facilement remplaçables par tes constantes de repanier.xlsx.xlsx_styles si souhaité)
    title_font = Font(bold=True, size=14, color="2A4329")
    section_font = Font(bold=True, size=11, color="2A4329")
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2A4329", end_color="2A4329", fill_type="solid")
    muted_font = Font(italic=True, color="666666")
    bold_font = Font(bold=True)

    # 1. En-tête du sondage
    ws["A1"] = poll.title
    ws["A1"].font = title_font

    ws["A2"] = _("Sent at")
    ws["B2"] = (
        timezone.localtime(poll.sent_at).strftime("%d/%m/%Y %H:%M")
        if poll.sent_at
        else _("Not sent yet")
    )

    ws["A3"] = _("Deadline")
    ws["B3"] = (
        timezone.localtime(poll.deadline).strftime("%d/%m/%Y %H:%M")
        if poll.deadline
        else _("None")
    )

    # 2. Tableau de synthèse des résultats
    total_invited = poll.responses.count()
    answered_count = poll.responses.filter(answered_at__isnull=False).count()
    unanswered_count = total_invited - answered_count

    ws["A5"] = _("Summary")
    ws["A5"].font = section_font

    summary_headers = [_("Choice"), _("Votes"), "%"]
    for col_idx, header in enumerate(summary_headers, start=1):
        cell = ws.cell(row=6, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        if col_idx > 1:
            cell.alignment = Alignment(horizontal="right")

    choices_with_counts = poll.choices.annotate(
        votes=Count("responses", filter=models.Q(responses__answered_at__isnull=False))
    )

    current_row = 7
    for choice in choices_with_counts:
        pct = round((choice.votes / total_invited) * 100, 1) if total_invited else 0
        ws.cell(row=current_row, column=1, value=choice.label)
        c_votes = ws.cell(row=current_row, column=2, value=choice.votes)
        c_votes.font = bold_font
        c_votes.alignment = Alignment(horizontal="right")
        c_pct = ws.cell(row=current_row, column=3, value=f"{pct}%")
        c_pct.alignment = Alignment(horizontal="right")
        current_row += 1

    # Ligne Sans réponse
    unanswered_pct = round((unanswered_count / total_invited) * 100, 1) if total_invited else 0
    c_no_resp = ws.cell(row=current_row, column=1, value=_("No response yet"))
    c_no_resp.font = muted_font
    c_no_votes = ws.cell(row=current_row, column=2, value=unanswered_count)
    c_no_votes.font = muted_font
    c_no_votes.alignment = Alignment(horizontal="right")
    c_no_pct = ws.cell(row=current_row, column=3, value=f"{unanswered_pct}%")
    c_no_pct.font = muted_font
    c_no_pct.alignment = Alignment(horizontal="right")

    # 3. Liste nominative détaillée
    current_row += 2
    ws.cell(row=current_row, column=1, value=_("Detailed responses")).font = section_font
    current_row += 1

    detail_headers = [
        _("Member"),
        _("Email"),
        _("Selected choice"),
        _("Comment"),
        _("Answered at"),
    ]
    for col_idx, header in enumerate(detail_headers, start=1):
        cell = ws.cell(row=current_row, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill

    responses = (
        poll.responses.select_related("customer__user", "choice")
        .order_by(
            models.F("answered_at").desc(nulls_last=True),
            "customer__short_basket_name",
        )
    )

    for resp in responses:
        current_row += 1
        email_addr = getattr(resp.customer.user, "email", "") if resp.customer.user else ""
        ws.cell(row=current_row, column=1, value=resp.customer.short_basket_name)
        ws.cell(row=current_row, column=2, value=email_addr)

        if resp.choice:
            ws.cell(row=current_row, column=3, value=resp.choice.label)
        else:
            c_empty = ws.cell(row=current_row, column=3, value=_("No response yet"))
            c_empty.font = muted_font

        ws.cell(row=current_row, column=4, value=resp.comment or "")
        ws.cell(
            row=current_row,
            column=5,
            value=(
                timezone.localtime(resp.answered_at).strftime("%d/%m/%Y %H:%M")
                if resp.answered_at
                else ""
            ),
        )

    # Ajustement automatique de la largeur des colonnes
    for col in ws.columns:
        max_length = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_length:
                max_length = len(val)
        ws.column_dimensions[col_letter].width = min(max(max_length + 3, 12), 55)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    filename = f"poll-{slugify(poll.title) or poll.pk}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response