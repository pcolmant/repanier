from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from repanier.models.poll import PollChoice, PollResponse, is_new_poll_enabled


def poll_vote(request, token):
    if not is_new_poll_enabled():
        raise Http404()

    poll_response = get_object_or_404(
        PollResponse.objects.select_related("poll", "customer", "choice").prefetch_related(
            "choices"
        ),
        token=token,
    )
    poll = poll_response.poll
    choices = list(poll.choices.all())
    allow_multiple = bool(getattr(poll, "allow_multiple", False))

    selected_choices = list(poll_response.choices.all())
    if not selected_choices and poll_response.choice:
        selected_choices = [poll_response.choice]

    if not poll.is_open:
        return render(
            request,
            "repanier/poll_confirm.html",
            {
                "poll": poll,
                "poll_response": poll_response,
                "choices": choices,
                "selected_choices": selected_choices,
                "allow_multiple": allow_multiple,
                "closed": True,
                "saved": False,
                "error_message": None,
            },
        )

    saved = False
    error_message = None

    if request.method == "POST":
        comment = request.POST.get("comment", "").strip()
        raw_ids = request.POST.getlist("choices")

        valid_ids = {str(c.id) for c in choices}
        selected_ids = [cid for cid in raw_ids if cid in valid_ids]

        if not allow_multiple and len(selected_ids) > 1:
            selected_ids = selected_ids[:1]

        if not selected_ids:
            error_message = _("Please select at least one option.")
        else:
            chosen_objs = [c for c in choices if str(c.id) in selected_ids]
            poll_response.choice = chosen_objs[0]
            poll_response.comment = comment
            poll_response.answered_at = timezone.now()
            poll_response.save(update_fields=["choice", "comment", "answered_at"])
            poll_response.choices.set(chosen_objs)
            selected_choices = chosen_objs
            saved = True

    selected_id_set = {c.id for c in selected_choices}

    return render(
        request,
        "repanier/poll_confirm.html",
        {
            "poll": poll,
            "poll_response": poll_response,
            "choices": choices,
            "selected_choices": selected_choices,
            "selected_id_set": selected_id_set,
            "allow_multiple": allow_multiple,
            "closed": False,
            "saved": saved,
            "error_message": error_message,
        },
    )