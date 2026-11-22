import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djangocms_text_ckeditor.fields import HTMLField

from repanier.const import EMPTY_STRING


def is_new_poll_enabled():
    return getattr(settings, "REPANIER_SETTINGS_REPANIER_POLL_ENABLED", False)


class Poll(models.Model):
    title = models.CharField(_("Title"), max_length=200)
    description = HTMLField(
        _("Message"),
        help_text=_("Rich HTML message included in the email sent to members."),
        configuration="CKEDITOR_SETTINGS_MODEL2",
        default=EMPTY_STRING,
        blank=True,
    )
    allow_multiple = models.BooleanField(
        _("Allow multiple choices"),
        default=False,
        help_text=_(
            "If checked, members can select several options instead of just one."
        ),
    )
    deadline = models.DateTimeField(
        _("Deadline"),
        null=True,
        blank=True,
        help_text=_("Optional closing date and time for responses."),
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    sent_at = models.DateTimeField(_("Sent at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Poll / Decision")
        verbose_name_plural = _("Polls / Decisions")
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

    @property
    def is_open(self):
        if self.deadline and timezone.now() > self.deadline:
            return False
        return True


class PollChoice(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name=_("Poll"),
    )
    label = models.CharField(_("Choice label"), max_length=150)
    order = models.PositiveSmallIntegerField(_("Order"), default=0)

    class Meta:
        verbose_name = _("Choice")
        verbose_name_plural = _("Choices")
        ordering = ("order", "id")

    def __str__(self):
        return self.label


class PollResponse(models.Model):
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name="responses",
        verbose_name=_("Poll"),
    )
    customer = models.ForeignKey(
        "repanier.Customer",
        on_delete=models.CASCADE,
        related_name="poll_responses",
        verbose_name=_("Member"),
    )
    choice = models.ForeignKey(
        PollChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responses",
        verbose_name=_("Selected choice"),
    )
    choices = models.ManyToManyField(
        PollChoice,
        blank=True,
        related_name="multi_responses",
        verbose_name=_("Selected choices"),
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    comment = models.TextField(_("Comment"), blank=True)
    answered_at = models.DateTimeField(_("Answered at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Response")
        verbose_name_plural = _("Responses")
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "customer"],
                name="unique_poll_customer_response",
            )
        ]

    def __str__(self):
        return f"{self.customer} - {self.poll}"