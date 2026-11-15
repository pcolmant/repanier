"""Audit the whole accounting history of the site. Read only.

Years of data, manual corrections, cancelled rounds, restored dumps:
the balances drift silently until someone notices. This command
replays the accounting algebra of Permanence.invoice() over all the
books and reports every discrepancy it can see - it changes nothing,
suggests repairs, and stays safe to run anywhere, anytime:

    ./manage.py audit_accounting
    ./manage.py audit_accounting --permanence 1736
    ./manage.py audit_accounting --customer alice@example.com
    ./manage.py audit_accounting --since 2018-01-01
    ./manage.py audit_accounting --invoice c:4785

--since compares the books of an era only (the rounds, their books,
the closure stamps, the profit corrections and the anchors of the
period): the customer and producer balance chains are identities
over the whole history, they never filter. --invoice replaces the
audit with the drill down of one book: the stored totals, every
purchase line, the recomputed sums (c: for a customer invoice,
p: for a producer one).

Six classes of invariants:

A. Customer accounts: the balance of every customer equals its
   initial balance, plus the bank movements attached to its invoices,
   minus the totals of its invoiced books (only the customer who pays
   is charged; the members of a group are not).
B. Producer accounts: the balance of every producer equals its
   initial balance, plus the totals of its invoiced books minus the
   profit corrections kept by the group (a claimed amount below the
   calculated amount), plus the bank movements attached to its
   invoices. A fully settled producer returns to zero. The
   corrections the books imply must also be the corrections the
   invoicing booked on the site consumer account.
C. Invoice totals: the totals of every invoiced book are recomputed
   from its purchases (selling price for the customers, purchase
   price for the producers), including transport and the Belgian
   rounding, and compared with the stored amounts; the
   customer-producer cross books are recomputed the same way. A
   book whose money columns all match but whose stored VAT does
   not is reported under C4 instead of C1/C2: no money moved, the
   drift of an old formula or a post-invoicing edit - documenting
   it is safer than repairing history.
D. Permanence totals: for every invoiced permanence, the amount
   charged to the customers equals the amount booked on the
   producers - the group keeps an equal share of both sides.
E. Closure: every invoice, purchase and anchor of an invoiced
   permanence carries the status and the anchor stamp of the round;
   a partially closed round leaks money.
F. The bank: exactly one LATEST_TOTAL anchor exists; each anchor of
   the chain nets the movements attached during its round (the
   profit corrections are not bank entries and never move it); every
   payment older than the latest anchor is attached to a book - an
   unattached payment is lost money.

The audit reads the balances and the totals as they are stored: when
a book keeps a wrong previous_balance, the replay inherits it. It
still catches the drift this book introduces at its own round.

Exit: 0 when every invariant holds, 1 when something needs a look.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import DecimalField, F, Q, Sum

from repanier.const import BankMovement, DECIMAL_ZERO, SaleStatus
from repanier.models.bankaccount import BankAccount
from repanier.models.customer import Customer
from repanier.models.invoice import (
    CustomerInvoice,
    CustomerProducerInvoice,
    ProducerInvoice,
)
from repanier.models.permanence import Permanence
from repanier.models.producer import Producer
from repanier.models.purchase import PurchaseWoReceiver
from repanier.tools import round_gov_be

INVOICED_STATUSES = [SaleStatus.INVOICED, SaleStatus.ARCHIVED]

MONEY = DecimalField(max_digits=10, decimal_places=2)
VAT = DecimalField(max_digits=10, decimal_places=4)
NOT_BANK_ENTRIES = [BankMovement.PROFIT, BankMovement.TAX]


class Finding:
    __slots__ = ("code", "reference", "message", "suggestion")

    def __init__(self, code, reference, message, suggestion):
        self.code = code
        self.reference = reference
        self.message = message
        self.suggestion = suggestion

    def __str__(self):
        return "[{}] {}: {} Suggested repair: {}".format(
            self.code, self.reference, self.message, self.suggestion
        )


def cents(amount):
    """The audit compares stored money: a null sum is an empty account."""
    if amount is None:
        return DECIMAL_ZERO
    return Decimal(amount)


def money_sum(query_set, expression, output):
    result = query_set.aggregate(total=Sum(expression, output_field=output))
    return cents(result["total"])


def net(value_in, value_out):
    return cents(value_in) - cents(value_out)


def charged_expression():
    """The total a charged book puts on its payer: Repanier calls it
    get_total_price_with_tax()."""
    return F("total_price_with_tax") + F("delta_price_with_tax") + F(
        "delta_transport"
    )


# ----------------------------------------------------------------- A


def audit_customer_accounts(customer_id=None):
    """Every customer balance, replayed from the bank and the books."""
    findings = []
    bank_net = {
        row["customer_id"]: net(row["bank_in"], row["bank_out"])
        for row in BankAccount.objects.filter(
            customer_invoice__isnull=False, customer__isnull=False
        )
        .values("customer_id")
        .annotate(bank_in=Sum("bank_amount_in", output_field=MONEY))
        .annotate(bank_out=Sum("bank_amount_out", output_field=MONEY))
    }
    charged_total = {
        row["customer_id"]: cents(row["charged"])
        for row in CustomerInvoice.objects.filter(
            customer_charged_id=F("customer_id"), status__in=INVOICED_STATUSES
        )
        .values("customer_id")
        .annotate(charged=Sum(charged_expression(), output_field=MONEY))
    }
    customers = Customer.objects.all()
    if customer_id is not None:
        customers = customers.filter(id=customer_id)
    for customer in customers.only(
        "id", "short_basket_name", "initial_balance", "balance"
    ):
        bank = bank_net.get(customer.id, DECIMAL_ZERO)
        charged = charged_total.get(customer.id, DECIMAL_ZERO)
        initial = cents(customer.initial_balance.amount)
        expected = initial + bank - charged
        stored = cents(customer.balance.amount)
        if expected != stored:
            findings.append(
                Finding(
                    "A1",
                    "customer {} ({})".format(
                        customer.id, customer.short_basket_name
                    ),
                    "stored balance {}, replayed {} (initial {}, bank"
                    " attached {}, invoiced orders {}).".format(
                        stored, expected, initial, bank, charged
                    ),
                    "compare the bank movements and the invoiced books of"
                    " this customer in the admin; the replay is what they"
                    " add up to.",
                )
            )
    return findings


# ----------------------------------------------------------------- B


def audit_producer_accounts(producer_id=None, since=None):
    """Every producer balance, replayed from its books and payments.

    The profit correction of a round (claimed amount below the
    calculated amount) reduces what the group owes: the books carry
    the calculated total, the correction moves both the producer
    balance and the site consumer account.
    """
    findings = []
    profit_delta = {}
    profit_by_round = {}
    invoiced_books = ProducerInvoice.objects.filter(
        status__in=INVOICED_STATUSES
    )
    if producer_id is not None:
        invoiced_books = invoiced_books.filter(producer_id=producer_id)
    for invoice in invoiced_books.only(
        "id",
        "permanence_id",
        "producer_id",
        "previous_balance",
        "total_price_with_tax",
        "delta_price_with_tax",
        "delta_transport",
        "to_be_paid",
        "to_be_invoiced_balance",
    ).select_related("producer"):
        total = (
            cents(invoice.total_price_with_tax.amount)
            + cents(invoice.delta_price_with_tax.amount)
            + cents(invoice.delta_transport.amount)
        )
        if invoice.to_be_paid and not invoice.producer.represent_this_buyinggroup:
            delta = (
                cents(invoice.previous_balance.amount)
                + total
                - cents(invoice.to_be_invoiced_balance.amount)
            )
            if delta != DECIMAL_ZERO:
                profit_delta[invoice.producer_id] = (
                    profit_delta.get(invoice.producer_id, DECIMAL_ZERO) + delta
                )
                profit_by_round[invoice.permanence_id] = (
                    profit_by_round.get(invoice.permanence_id, DECIMAL_ZERO) + delta
                )
    invoiced_total = {
        row["producer_id"]: cents(row["total"])
        for row in invoiced_books.values("producer_id").annotate(
            total=Sum(charged_expression(), output_field=MONEY)
        )
    }
    bank_net = {
        row["producer_id"]: net(row["bank_in"], row["bank_out"])
        for row in BankAccount.objects.filter(
            producer_invoice__isnull=False, producer__isnull=False
        )
        .values("producer_id")
        .annotate(bank_in=Sum("bank_amount_in", output_field=MONEY))
        .annotate(bank_out=Sum("bank_amount_out", output_field=MONEY))
    }
    producers = Producer.objects.all()
    if producer_id is not None:
        producers = producers.filter(id=producer_id)
    for producer in producers.only(
        "id", "short_profile_name", "initial_balance", "balance"
    ):
        initial = cents(producer.initial_balance.amount)
        invoiced = invoiced_total.get(producer.id, DECIMAL_ZERO)
        profit = profit_delta.get(producer.id, DECIMAL_ZERO)
        bank = bank_net.get(producer.id, DECIMAL_ZERO)
        expected = initial + invoiced - profit + bank
        stored = cents(producer.balance.amount)
        if expected != stored:
            findings.append(
                Finding(
                    "B1",
                    "producer {} ({})".format(
                        producer.id, producer.short_profile_name
                    ),
                    "stored balance {}, replayed {} (initial {}, invoiced"
                    " books {}, profit corrections {}, bank attached {}).".format(
                        stored, expected, initial, invoiced, profit, bank
                    ),
                    "compare the invoiced books and the bank movements of"
                    " this producer in the admin.",
                )
            )
    # The corrections the books imply must be the corrections the
    # invoicing booked on the site consumer account: when a claimed
    # amount no longer matches the books, the PROFIT row lies.
    if producer_id is None:
        booked_by_round = {
            row["permanence_id"]: net(row["bank_in"], row["bank_out"])
            for row in BankAccount.objects.filter(
                operation_status__in=NOT_BANK_ENTRIES, permanence__isnull=False
            )
            .values("permanence_id")
            .annotate(bank_in=Sum("bank_amount_in", output_field=MONEY))
            .annotate(bank_out=Sum("bank_amount_out", output_field=MONEY))
        }
        if since is not None:
            era_rounds = set(
                Permanence.objects.filter(permanence_date__gte=since).values_list(
                    "id", flat=True
                )
            )
        rounds_to_check = set(booked_by_round) | set(profit_by_round)
        if since is not None:
            rounds_to_check &= era_rounds
        for permanence_id in sorted(rounds_to_check):
            permanence = (
                Permanence.objects.filter(id=permanence_id)
                .only("id", "permanence_date", "short_name_v2")
                .first()
            )
            booked = booked_by_round.get(permanence_id, DECIMAL_ZERO)
            implied = profit_by_round.get(permanence_id, DECIMAL_ZERO)
            if booked != implied:
                findings.append(
                    Finding(
                        "B2",
                        "permanence {} (id {})".format(permanence, permanence_id),
                        "the books imply a correction of {}, the invoicing"
                        " booked {} on the site consumer account.".format(
                            implied, booked
                        ),
                        "a claimed amount or a book total was edited after the"
                        " invoicing: compare them with the bank correction"
                        " line of this round.",
                    )
                )
    return findings


# ----------------------------------------------------------------- C


def replay_customer_invoice(invoice):
    """What calculate_order_amount recomputes from the purchases.

    Straight out of the model: the purchases, then the transport on
    the payer book, then the Belgian rounding correction.
    """
    if invoice.is_group:
        query_set = PurchaseWoReceiver.objects.filter(
            permanence_id=invoice.permanence_id,
            customer_invoice__customer_charged_id=invoice.customer_id,
        )
    else:
        query_set = PurchaseWoReceiver.objects.filter(
            permanence_id=invoice.permanence_id,
            customer_id=invoice.customer_id,
        )
    result = query_set.aggregate(
        selling_price=Sum("selling_price", output_field=MONEY),
        customer_vat=Sum("customer_vat", output_field=VAT),
        deposit=Sum("deposit", output_field=MONEY),
    )
    total_price = cents(result["selling_price"])
    total_vat = cents(result["customer_vat"])
    total_deposit = cents(result["deposit"])
    delta_price = DECIMAL_ZERO
    delta_transport = DECIMAL_ZERO
    if (
        invoice.customer_id == invoice.customer_charged_id
        and invoice.transport.amount != DECIMAL_ZERO
    ):
        with_total = total_price
        if with_total != DECIMAL_ZERO:
            if invoice.min_transport.amount == DECIMAL_ZERO:
                delta_transport = invoice.transport.amount
            elif with_total < invoice.min_transport.amount:
                delta_transport = min(
                    invoice.min_transport.amount - with_total,
                    invoice.transport.amount,
                )
        # An empty basket is never charged a transport.
    if settings.REPANIER_SETTINGS_ROUND_INVOICES:
        total_rounded = total_price + delta_price + delta_transport
        delta_price += round_gov_be(total_rounded) - total_rounded
    return total_price, total_vat, total_deposit, delta_price, delta_transport


def audit_invoice_purchase_totals(permanence_id=None, since=None):
    """Every invoiced book, recomputed from the purchases."""
    findings = []
    customer_invoices = CustomerInvoice.objects.filter(
        permanence__status__in=INVOICED_STATUSES
    )
    if since is not None:
        customer_invoices = customer_invoices.filter(
            permanence__permanence_date__gte=since
        )
    if permanence_id is not None:
        customer_invoices = customer_invoices.filter(
            permanence_id=permanence_id
        )
    for invoice in customer_invoices.select_related("permanence").only(
        "id",
        "permanence_id",
        "customer_id",
        "customer_charged_id",
        "is_group",
        "total_price_with_tax",
        "total_vat",
        "total_deposit",
        "delta_price_with_tax",
        "delta_transport",
        "transport",
        "min_transport",
        "permanence__id",
        "permanence__permanence_date",
    "permanence__short_name_v2",
    ):
        (
            total_price,
            total_vat,
            total_deposit,
            delta_price,
            delta_transport,
        ) = replay_customer_invoice(invoice)
        reference = "customer invoice {} of {}".format(
            invoice.id, invoice.permanence
        )
        stored_vat = cents(invoice.total_vat.amount)
        money_mismatches = [
            "{} {} instead of {}".format(label, stored, expected)
            for stored, expected, label in (
                (
                    cents(invoice.total_price_with_tax.amount),
                    total_price,
                    "total",
                ),
                (cents(invoice.delta_price_with_tax.amount), delta_price, "delta"),
                (cents(invoice.delta_transport.amount), delta_transport, "transport"),
                (cents(invoice.total_deposit.amount), total_deposit, "deposit"),
            )
            if stored != expected
        ]
        vat_drifted = stored_vat != total_vat
        if money_mismatches:
            if vat_drifted:
                money_mismatches.append(
                    "vat {} instead of {}".format(stored_vat, total_vat)
                )
            findings.append(
                Finding(
                    "C1",
                    reference,
                    "; ".join(money_mismatches) + " (recomputed from the purchases).",
                    "check the purchases of this book; the stored amounts no"
                    " longer match what the purchases add up to.",
                )
            )
        elif vat_drifted:
            findings.append(
                Finding(
                    "C4",
                    reference,
                    "vat {} instead of {} (recomputed from the purchase"
                    " lines); every money column matches.".format(
                        stored_vat, total_vat
                    ),
                    "no money moved: the stored VAT no longer matches the"
                    " vat of the purchase lines - an older formula or a"
                    " post-invoicing edit. Document it, repairing history"
                    " is riskier than the drift.",
                )
            )

    producer_invoices = ProducerInvoice.objects.filter(
        permanence__status__in=INVOICED_STATUSES
    )
    if since is not None:
        producer_invoices = producer_invoices.filter(
            permanence__permanence_date__gte=since
        )
    if permanence_id is not None:
        producer_invoices = producer_invoices.filter(
            permanence_id=permanence_id
        )
    for invoice in producer_invoices.select_related(
        "producer", "permanence"
    ).only(
        "id",
        "permanence_id",
        "producer_id",
        "total_price_with_tax",
        "total_vat",
        "total_deposit",
        "delta_price_with_tax",
        "delta_transport",
        "delta_vat",
        "producer__represent_this_buyinggroup",
        "permanence__id",
        "permanence__permanence_date",
    "permanence__short_name_v2",
    ):
        result = PurchaseWoReceiver.objects.filter(
            permanence_id=invoice.permanence_id,
            producer_id=invoice.producer_id,
        ).aggregate(
            purchase_price=Sum("purchase_price", output_field=MONEY),
            producer_vat=Sum("producer_vat", output_field=VAT),
            deposit=Sum("deposit", output_field=MONEY),
        )
        reference = "producer invoice {} of {}".format(
            invoice.id, invoice.permanence
        )
        money_mismatches = [
            "{} {} instead of {}".format(label, stored, expected)
            for stored, expected, label in (
                (
                    cents(invoice.total_price_with_tax.amount),
                    cents(result["purchase_price"]),
                    "total",
                ),
                (
                    cents(invoice.total_deposit.amount),
                    cents(result["deposit"]),
                    "deposit",
                ),
            )
            if stored != expected
        ]
        vat_mismatches = []
        if cents(invoice.total_vat.amount) != cents(result["producer_vat"]):
            vat_mismatches.append(
                "vat {} instead of {}".format(
                    cents(invoice.total_vat.amount), cents(result["producer_vat"])
                )
            )
        if invoice.producer.represent_this_buyinggroup:
            # The site producer book carries the customer deltas of the
            # round: the group keeps the transport and the corrections.
            deltas = CustomerInvoice.objects.filter(
                permanence_id=invoice.permanence_id
            ).aggregate(
                delta_price=Sum("delta_price_with_tax", output_field=MONEY),
                delta_transport=Sum("delta_transport", output_field=MONEY),
                delta_vat=Sum("delta_vat", output_field=VAT),
            )
            money_mismatches += [
                "{} {} instead of {}".format(label, stored, expected)
                for stored, expected, label in (
                    (
                        cents(invoice.delta_price_with_tax.amount),
                        cents(deltas["delta_price"]),
                        "delta",
                    ),
                    (
                        cents(invoice.delta_transport.amount),
                        cents(deltas["delta_transport"]),
                        "transport",
                    ),
                )
                if stored != expected
            ]
            if cents(invoice.delta_vat.amount) != cents(deltas["delta_vat"]):
                vat_mismatches.append(
                    "vat to add {} instead of {}".format(
                        cents(invoice.delta_vat.amount), cents(deltas["delta_vat"])
                    )
                )
        if money_mismatches:
            findings.append(
                Finding(
                    "C2",
                    reference,
                    "; ".join(money_mismatches + vat_mismatches)
                    + " (recomputed from the purchases).",
                    "check the purchases of this book; the stored amounts no"
                    " longer match what the purchases add up to.",
                )
            )
        elif vat_mismatches:
            findings.append(
                Finding(
                    "C4",
                    reference,
                    "; ".join(vat_mismatches)
                    + " (recomputed from the purchase lines); every money"
                    " column matches.",
                    "no money moved: the stored VAT no longer matches the"
                    " vat of the purchase lines - an older formula or a"
                    " post-invoicing edit. Document it, repairing history"
                    " is riskier than the drift.",
                )
            )

    cross_invoices = CustomerProducerInvoice.objects.filter(
        permanence__status__in=INVOICED_STATUSES
    )
    if since is not None:
        cross_invoices = cross_invoices.filter(
            permanence__permanence_date__gte=since
        )
    if permanence_id is not None:
        cross_invoices = cross_invoices.filter(permanence_id=permanence_id)
    for invoice in cross_invoices.select_related("permanence").only(
        "id",
        "permanence_id",
        "customer_id",
        "producer_id",
        "total_purchase_with_tax",
        "total_selling_with_tax",
        "permanence__id",
        "permanence__permanence_date",
    "permanence__short_name_v2",
    ):
        result = PurchaseWoReceiver.objects.filter(
            permanence_id=invoice.permanence_id,
            customer_id=invoice.customer_id,
            producer_id=invoice.producer_id,
        ).aggregate(
            purchase_price=Sum("purchase_price", output_field=MONEY),
            selling_price=Sum("selling_price", output_field=MONEY),
        )
        store = [
            (
                cents(invoice.total_purchase_with_tax.amount),
                cents(result["purchase_price"]),
                "producer amount",
            ),
            (
                cents(invoice.total_selling_with_tax.amount),
                cents(result["selling_price"]),
                "customer amount",
            ),
        ]
        mismatches = [
            "{} {} instead of {}".format(label, stored, expected)
            for stored, expected, label in store
            if stored != expected
        ]
        if mismatches:
            findings.append(
                Finding(
                    "C3",
                    "cross book {} of {}".format(invoice.id, invoice.permanence),
                    "; ".join(mismatches) + " (recomputed from the purchases).",
                    "check the purchases behind this cross book.",
                )
            )
    return findings


# ----------------------------------------------------------------- D


def audit_permanence_totals(permanence_id=None, since=None):
    """Charged to the customers == booked on the producers."""
    findings = []
    invoiced = Permanence.objects.filter(status__in=INVOICED_STATUSES).order_by(
        "permanence_date", "id"
    )
    if since is not None:
        invoiced = invoiced.filter(permanence_date__gte=since)
    if permanence_id is not None:
        invoiced = invoiced.filter(id=permanence_id)
    for permanence in invoiced.only(
        "id", "permanence_date", "short_name_v2"
    ):
        charged = money_sum(
            CustomerInvoice.objects.filter(
                permanence_id=permanence.id,
                customer_charged_id=F("customer_id"),
                status__in=INVOICED_STATUSES,
            ),
            charged_expression(),
            MONEY,
        )
        booked = money_sum(
            ProducerInvoice.objects.filter(
                permanence_id=permanence.id, status__in=INVOICED_STATUSES
            ),
            charged_expression(),
            MONEY,
        )
        if charged != booked:
            findings.append(
                Finding(
                    "D1",
                    "permanence {} (id {})".format(permanence, permanence.id),
                    "charged to the customers {}, booked on the producers {};"
                    " the difference {} has no explanation.".format(
                        charged, booked, charged - booked
                    ),
                    "compare the invoices of this round: one side carries an"
                    " amount the other side does not.",
                )
            )
    return findings


# ----------------------------------------------------------------- E


def audit_permanence_closure(permanence_id=None, since=None):
    """A round is fully closed or leaks money."""
    findings = []

    def closed_book(kind, invoice, permanence, code_status, code_stamp):
        status_finding = invoice.status != permanence.status
        stamp_finding = invoice.invoice_sort_order != permanence.invoice_sort_order
        if status_finding:
            findings.append(
                Finding(
                    code_status,
                    "{} invoice {} of {}".format(
                        kind, invoice.id, permanence
                    ),
                    "status {} instead of the round status {}.".format(
                        invoice.status, permanence.status
                    ),
                    "a book of this round lives outside the round; its"
                    " totals may be incomplete.",
                )
            )
        if stamp_finding:
            findings.append(
                Finding(
                    code_stamp,
                    "{} invoice {} of {}".format(kind, invoice.id, permanence),
                    "stamped with anchor {} instead of {}.".format(
                        invoice.invoice_sort_order, permanence.invoice_sort_order
                    ),
                    "the book belongs to another round or escaped the"
                    " stamping at invoicing time.",
                )
            )

    invoiced = Permanence.objects.filter(status__in=INVOICED_STATUSES).order_by(
        "permanence_date", "id"
    )
    if since is not None:
        invoiced = invoiced.filter(permanence_date__gte=since)
    if permanence_id is not None:
        invoiced = invoiced.filter(id=permanence_id)
    for permanence in invoiced.only(
        "id",
        "status",
        "permanence_date",
        "short_name_v2",
        "invoice_sort_order",
    ):
        if permanence.invoice_sort_order is None:
            findings.append(
                Finding(
                    "E1",
                    "permanence {} (id {})".format(permanence, permanence.id),
                    "invoiced without the bank anchor stamp"
                    " (invoice_sort_order is null).",
                    "this round was invoiced but never chained to the bank;"
                    " check its history before trusting its totals.",
                )
            )
            continue
        for invoice in CustomerInvoice.objects.filter(
            permanence_id=permanence.id
        ).only("id", "status", "invoice_sort_order"):
            closed_book("customer", invoice, permanence, "E2", "E3")
        for invoice in ProducerInvoice.objects.filter(
            permanence_id=permanence.id
        ).only("id", "status", "invoice_sort_order"):
            closed_book("producer", invoice, permanence, "E4", "E5")
        purchases = PurchaseWoReceiver.objects.filter(
            permanence_id=permanence.id
        ).exclude(status=permanence.status)
        if purchases.exists():
            findings.append(
                Finding(
                    "E6",
                    "permanence {} (id {})".format(permanence, permanence.id),
                    "{} purchases still live outside the closed round.".format(
                        purchases.count()
                    ),
                    "re-open the round, or check the lines the closing left"
                    " behind.",
                )
            )
    return findings


# ----------------------------------------------------------------- F


def audit_bank(since=None):
    """The anchor chain and the attached payments.

    With --since, the chain compares the anchors of the era only:
    the first anchor of the era opens it and is never compared -
    the eras before it are the business of another run.
    """
    findings = []
    latest_count = BankAccount.objects.filter(
        operation_status=BankMovement.LATEST_TOTAL
    ).count()
    if latest_count != 1:
        findings.append(
            Finding(
                "F1",
                "bank account",
                "{} rows claim to be the LATEST_TOTAL anchor, exactly one"
                " must.".format(latest_count),
                "the invoicing chain is broken: cancel the latest rounds,"
                " or fix the operation_status of the impostors.",
            )
        )
    anchors = list(
        BankAccount.objects.filter(
            customer__isnull=True, producer__isnull=True
        )
        .exclude(operation_status__in=NOT_BANK_ENTRIES)
        .order_by("operation_date", "id")
        .only(
            "id",
            "permanence_id",
            "operation_date",
            "bank_amount_in",
            "bank_amount_out",
        )
    )
    if since is not None:
        # The eras are the business of their own run: the first
        # anchor of the era opens it and is never compared.
        anchors = [
            anchor for anchor in anchors if anchor.operation_date >= since
        ]
    if not anchors:
        return findings
    # None until the era has a baseline anchor: the first invoiced
    # anchor of the run carries no comparison.
    previous_net = None
    for anchor in anchors:
        anchor_net = net(anchor.bank_amount_in.amount, anchor.bank_amount_out.amount)
        if anchor.permanence_id is None:
            # The opening anchor carries no chain - but it balances
            # the era which starts from it.
            previous_net = anchor_net
            continue
        permanence = (
            Permanence.objects.filter(id=anchor.permanence_id)
            .only("id", "status", "permanence_date", "short_name_v2")
            .first()
        )
        if permanence is None or permanence.status not in INVOICED_STATUSES:
            previous_net = anchor_net
            continue
        attached = money_sum(
            BankAccount.objects.filter(
                permanence_id=anchor.permanence_id,
                operation_status__in=[
                    BankMovement.NOT_LATEST_TOTAL,
                    BankMovement.CALCULATED_INVOICE,
                    BankMovement.COMPENSATION,
                    BankMovement.MEMBERSHIP_FEE,
                ],
            ).filter(
                Q(customer_invoice__isnull=False)
                | Q(producer_invoice__isnull=False)
            ),
            F("bank_amount_in") - F("bank_amount_out"),
            MONEY,
        )
        if previous_net is not None:
            expected = previous_net + attached
            if anchor_net != expected:
                findings.append(
                    Finding(
                        "F2",
                        "bank anchor {} of permanence {} (id {})".format(
                            anchor.id, permanence, permanence.id
                        ),
                        "net {}, the chain replays {} (previous anchor {},"
                        " movements attached during the round {}).".format(
                            anchor_net, expected, previous_net, attached
                        ),
                        "a bank movement of this round escaped the count:"
                        " compare the round with its bank lines.",
                    )
                )
        previous_net = anchor_net
    latest_date = anchors[-1].operation_date
    # A payment dated strictly before the latest anchor must have been
    # attached during a round - unless its permanence still waits below
    # invoiced (a cancelled round re-invoices everything later).  The
    # rows dated on the latest anchor day wait for the next round.
    lost = (
        BankAccount.objects.filter(
            customer_invoice__isnull=True,
            producer_invoice__isnull=True,
            operation_date__lt=latest_date,
        )
        .filter(Q(customer__isnull=False) | Q(producer__isnull=False))
        .exclude(operation_status__in=NOT_BANK_ENTRIES)
        .filter(
            Q(permanence__isnull=True)
            | Q(permanence__status__in=INVOICED_STATUSES)
            | Q(permanence__status=SaleStatus.CANCELLED)
        )
    )
    if since is not None:
        # The rows lost before the era are the business of another run.
        lost = lost.filter(operation_date__gte=since)
    if lost.exists():
        sample = list(
            lost.order_by("operation_date", "id")
            .only("id", "operation_date", "operation_comment")
            [:10]
        )
        illustration = "; ".join(
            "#{} {} {}".format(
                row.id, row.operation_date, row.operation_comment
            )
            for row in sample
        )
        findings.append(
            Finding(
                "F3",
                "bank account",
                "{} bank movements dated before the latest anchor ({}) are"
                " attached to no book, e.g. {}.".format(
                    lost.count(), latest_date, illustration
                ),
                "these payments never entered a round: check them in the"
                " admin (a restored dump or a manual edit may explain"
                " them).",
            )
        )
    return findings


# -----------------------------------------------------------------


def drill_down_invoice(kind, invoice_id):
    """One book, line by line: stored totals vs the purchases.

    Returns the lines to print; raises CommandError when the book
    does not exist. Pure analysis: nothing is written.
    """
    lines = []
    if kind == "c":
        invoice = (
            CustomerInvoice.objects.select_related("permanence")
            .only(
                "id",
                "permanence_id",
                "customer_id",
                "customer_charged_id",
                "is_group",
                "total_price_with_tax",
                "total_vat",
                "total_deposit",
                "delta_price_with_tax",
                "delta_transport",
                "transport",
                "min_transport",
                "permanence__id",
                "permanence__permanence_date",
                "permanence__short_name_v2",
            )
            .filter(id=invoice_id)
            .first()
        )
        if invoice is None:
            raise CommandError("no customer invoice with id {}".format(invoice_id))
        if invoice.is_group:
            purchases = PurchaseWoReceiver.objects.filter(
                permanence_id=invoice.permanence_id,
                customer_invoice__customer_charged_id=invoice.customer_id,
            )
        else:
            purchases = PurchaseWoReceiver.objects.filter(
                permanence_id=invoice.permanence_id,
                customer_id=invoice.customer_id,
            )
        total_price, total_vat, total_deposit, delta_price, delta_transport = (
            replay_customer_invoice(invoice)
        )
        lines.append(
            "customer invoice {} of {} (customer {})".format(
                invoice.id, invoice.permanence, invoice.customer_id
            )
        )
        verdict = (
            "OK - the purchases add up to the stored totals"
            if (total_price, total_vat, total_deposit, delta_price, delta_transport)
            == (
                cents(invoice.total_price_with_tax.amount),
                cents(invoice.total_vat.amount),
                cents(invoice.total_deposit.amount),
                cents(invoice.delta_price_with_tax.amount),
                cents(invoice.delta_transport.amount),
            )
            else "MISMATCH - the purchases no longer add up to the stored totals"
        )
        lines.append(
            "  stored total {}, vat {}, deposit {}, delta {}, transport {};"
            " replayed total {}, vat {}, deposit {}, delta {}, transport {} - {}."
            "".format(
                cents(invoice.total_price_with_tax.amount),
                cents(invoice.total_vat.amount),
                cents(invoice.total_deposit.amount),
                cents(invoice.delta_price_with_tax.amount),
                cents(invoice.delta_transport.amount),
                total_price,
                total_vat,
                total_deposit,
                delta_price,
                delta_transport,
                verdict,
            )
        )
        for purchase in purchases.select_related("offer_item").only(
            "id",
            "offer_item_id",
            "quantity_invoiced",
            "selling_price",
            "customer_vat",
            "deposit",
            "offer_item__long_name_v2",
        ).order_by("id"):
            lines.append(
                "  purchase #{} - {} - qty {}, selling {}, vat {}, deposit {}"
                "".format(
                    purchase.id,
                    purchase.offer_item.long_name_v2,
                    purchase.quantity_invoiced,
                    purchase.selling_price,
                    purchase.customer_vat,
                    purchase.deposit,
                )
            )
    else:
        invoice = (
            ProducerInvoice.objects.select_related("permanence", "producer")
            .only(
                "id",
                "permanence_id",
                "producer_id",
                "total_price_with_tax",
                "total_vat",
                "total_deposit",
                "delta_price_with_tax",
                "delta_transport",
                "producer__short_profile_name",
                "producer__represent_this_buyinggroup",
                "permanence__id",
                "permanence__permanence_date",
                "permanence__short_name_v2",
            )
            .filter(id=invoice_id)
            .first()
        )
        if invoice is None:
            raise CommandError("no producer invoice with id {}".format(invoice_id))
        purchases = PurchaseWoReceiver.objects.filter(
            permanence_id=invoice.permanence_id, producer_id=invoice.producer_id
        )
        result = purchases.aggregate(
            purchase_price=Sum("purchase_price", output_field=MONEY),
            producer_vat=Sum("producer_vat", output_field=VAT),
            deposit=Sum("deposit", output_field=MONEY),
        )
        total_price = cents(result["purchase_price"])
        total_vat = cents(result["producer_vat"])
        total_deposit = cents(result["deposit"])
        lines.append(
            "producer invoice {} of {} (producer {})".format(
                invoice.id,
                invoice.permanence,
                invoice.producer.short_profile_name,
            )
        )
        verdict = (
            "OK - the purchases add up to the stored totals"
            if (total_price, total_vat, total_deposit)
            == (
                cents(invoice.total_price_with_tax.amount),
                cents(invoice.total_vat.amount),
                cents(invoice.total_deposit.amount),
            )
            else "MISMATCH - the purchases no longer add up to the stored totals"
        )
        lines.append(
            "  stored total {}, vat {}, deposit {}; replayed total {}, vat {},"
            " deposit {} - {}.".format(
                cents(invoice.total_price_with_tax.amount),
                cents(invoice.total_vat.amount),
                cents(invoice.total_deposit.amount),
                total_price,
                total_vat,
                total_deposit,
                verdict,
            )
        )
        lines.append(
            "  site producer book: the customer deltas of the round ride"
            " on the customer books - compare them in the admin."
            if invoice.producer.represent_this_buyinggroup
            else "  the delta price ({}) and transport ({}) stay on this"
            " book.".format(
                invoice.delta_price_with_tax, invoice.delta_transport
            )
        )
        for purchase in purchases.select_related("offer_item").only(
            "id",
            "offer_item_id",
            "quantity_invoiced",
            "purchase_price",
            "producer_vat",
            "deposit",
            "offer_item__long_name_v2",
        ).order_by("id"):
            lines.append(
                "  purchase #{} - {} - qty {}, purchase {}, vat {}, deposit {}"
                "".format(
                    purchase.id,
                    purchase.offer_item.long_name_v2,
                    purchase.quantity_invoiced,
                    purchase.purchase_price,
                    purchase.producer_vat,
                    purchase.deposit,
                )
            )
    return lines


class Command(BaseCommand):
    help = (
        "Replay the accounting of the site over all its history. Read only:"
        " balance chains, book totals, round totals, closure, bank anchor."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--permanence",
            type=int,
            help="Audit only the books of this permanence id.",
        )
        parser.add_argument(
            "--customer",
            help="Audit only this customer (email of the login or id).",
        )
        parser.add_argument(
            "--since",
            help=(
                "Audit the era starting at this invoicing date (YYYY-MM-DD):"
                " books, round totals, closures and bank anchors of that"
                " era only. The balance identities (A, B1) stay lifetime."
            ),
        )
        parser.add_argument(
            "--invoice",
            help=(
                "Print one book line by line instead of auditing:"
                " c:<id> for a customer invoice, p:<id> for a producer"
                " one (the default is customer)."
            ),
        )

    def handle(self, *args, **options):
        if options["invoice"]:
            invoice_filter = options["invoice"]
            if invoice_filter.startswith("p:"):
                kind = "p"
                invoice_id = invoice_filter[2:]
            elif invoice_filter.startswith("c:"):
                kind = "c"
                invoice_id = invoice_filter[2:]
            else:
                kind = "c"
                invoice_id = invoice_filter
            if not invoice_id:
                raise CommandError("--invoice needs an invoice id")
            try:
                invoice_id = int(invoice_id)
            except ValueError:
                raise CommandError("--invoice needs a numeric invoice id")
            for line in drill_down_invoice(kind, invoice_id):
                self.stdout.write(line)
            return
        since = None
        if options["since"]:
            try:
                since = datetime.date.fromisoformat(options["since"])
            except ValueError:
                raise CommandError(
                    "--since expects a date like 2024-01-31, not {}".format(
                        options["since"]
                    )
                )
        permanence_id = options["permanence"]
        customer_id = None
        if options["customer"]:
            customer_filter = options["customer"]
            if customer_filter.isdigit():
                customer_id = int(customer_filter)
            else:
                from django.contrib.auth.models import User

                user = (
                    User.objects.filter(username__iexact=customer_filter)
                    .only("id")
                    .first()
                )
                if user is None or not Customer.objects.filter(
                    user_id=user.id
                ).exists():
                    raise CommandError(
                        "no customer with login {}".format(customer_filter)
                    )
                customer_id = Customer.objects.get(user_id=user.id).id
        audits = [
            ("A. Customer accounts", lambda: audit_customer_accounts(customer_id)),
            (
                "B. Producer accounts",
                lambda: audit_producer_accounts(since=since),
            ),
            (
                "C. Book totals recomputed from the purchases",
                lambda: audit_invoice_purchase_totals(permanence_id, since=since),
            ),
            (
                "D. Round totals customers vs producers",
                lambda: audit_permanence_totals(permanence_id, since=since),
            ),
            (
                "E. Closure of the invoiced rounds",
                lambda: audit_permanence_closure(permanence_id, since=since),
            ),
            ("F. The bank anchor chain", lambda: audit_bank(since=since)),
        ]
        finding_count = 0
        for title, audit in audits:
            self.stdout.write(title)
            findings = audit()
            for finding in findings[:20]:
                self.stdout.write(self.style.ERROR("  {}".format(finding)))
            if len(findings) > 20:
                self.stdout.write(
                    self.style.ERROR(
                        "  ... and {} more findings".format(len(findings) - 20)
                    )
                )
            self.stdout.write("  {} finding(s).".format(len(findings)))
            finding_count += len(findings)
        if finding_count:
            raise CommandError(
                "{} accounting finding(s): read the report above. The audit"
                " changed nothing - each finding carries a suggested"
                " repair.".format(finding_count)
            )
        self.stdout.write(
            "repanier audit accounting : the whole history replays square."
        )
