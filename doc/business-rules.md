# Repanier business rules

> **English version.** This is the reference edition; the French
> translation is [`règles-métier.md`](règles-métier.md). The two files
> are updated in the same PR: in case of divergence, this one prevails.

This document lists the business rules identified in the code and
(progressively) locked by the test suite (`repanier/tests/`). Code
references tell where each rule lives; test references tell where it is
verified.

---

## Part 1 - Classic business rules

### The purchase chain

A purchase (Purchase) binds together **one customer invoice**
(CustomerInvoice), **one producer invoice** (ProducerInvoice) and **one
customer-producer invoice** (CustomerProducerInvoice). The three are
created automatically on the first purchase of the (customer, offer)
pair (`Purchase.save`, signals/purchase.py).

The `pre_save` signal of Purchase recomputes the prices on every save:
`(customer unit price + deposit) x quantity` for the customer,
`(producer unit price + deposit) x quantity` for the producer, VAT on
both sides, invoice totals updated by delta.
Test: `test_purchase_flow.py`.

### Prices and VAT

- The customer price is **always derived** from the producer price:
  `customer price = producer price x multiplier` (Producer
  price_list_multiplier, applied in `Item.recalculate_prices`). The
  price typed on the product is never the reference.
- The producer communicates prices **excluding or including VAT**
  (`Producer.producer_price_are_wo_vat`). The asymmetric recalculation
  formulas (adding VAT on the wo-VAT price vs extracting VAT from the
  incl-VAT price) live in `Item.recalculate_prices`.
- VAT by brackets (`Vat`: 0%, 2.5%, 3.8%, 6%, 8%, 12%, 21%),
  quantized to 4 decimals; prices at 2 decimals.
- **No VAT ever applies to deposits**: the deposit is added to the unit
  price after the VAT computation.
  Tests: `test_vat_matrix.py`.

### Transport (delivery fee)

When the customer order is below the rebate threshold
(`min_transport`), a delivery fee applies, capped both by the amount
missing to reach the threshold and by the fee amount
(`CustomerInvoice.calculate_order_transport`). No fee on an empty
order; no fee for a group member (the group payer carries them).
Tests: `test_invoice_calculation.py`.

### Cash rounding (Belgium)

When `REPANIER_SETTINGS_ROUND_INVOICES` is active, the final total is
rounded to the nearest multiple of 0.05 \u20ac (`tools.round_gov_be`,
the official rule); the delta lands in `delta_price_with_tax`.
Tests: `test_tools.py`, `test_invoice_calculation.py`.

### Stock

An order cannot exceed the available stock minus what is already
reserved (offer_item.get_q_alert); decreasing below the already-sold
quantity is refused. Test: `test_purchase_flow.py`.

### The permanence life cycle

`PLANNED -> (WAIT_FOR_OPEN) -> OPENED -> (WAIT_FOR_CLOSED) -> CLOSED
-> (WAIT_FOR_SEND) -> SEND -> INVOICED -> ARCHIVED`
(`Permanence.set_status`, `task_order.open_order`, `close_order`).
`highest_status` never goes down: it memorizes the highest state
reached. Any inconsistent transition raises `ValueError`. Cancelling
an invoicing (`cancel_invoice`) brings the permanence back from
INVOICED to SEND (see "Cancellation" in part 2).
Tests: `test_status_flow.py`, `test_order_journey.py`.

### Automatic closure

A permanence flagged `automatically_closed` is closed (and its orders
sent) by the cron without any manual action.

---

## Part 2 - Signature business rules (the heart of Repanier)

### The group and its delivery point

A group is a customer (`Customer.is_group`) **bound to a delivery
point** (`LUT_DeliveryPoint.group`). The members of the group
(`Customer.group`) get the group's delivery board **by default** when
ordering: that point routes both the logistics AND the billing
(`CustomerInvoice.set_order_delivery`).

Two charging models:

- **individual payment**: `customer_charged == customer`;
- **group billing**: members order individually, but every member
  invoice points to the group (`customer_charged == group`), and the
  group invoice **aggregates** the purchases imputed to it. After
  invoicing: the group balance is debited, **the member balances do
  not move**. Tests: `test_invoicing.py` (GroupInvoicingTest).

### Closing a permanence delivery point by delivery point

A permanence with delivery points can be closed **for one or several
points only** (`close_order(everything=False, deliveries_id=[...])`):
the customers of the closed point are blocked, the permanence **stays
open** for the other points, which keep accepting orders. The full
closure (every point) moves the permanence to SEND.
Test: `test_invoicing.py` (PartialDeliveryPointClosureTest).

### The rule of three

Split a delivered product between the consumers **pro rata** so that
the total billed to the consumers matches, to the cent, the amount
billed by the producer. Example: 10 kg ordered, the producer delivers
10.5 kg but bills 10 - everyone receives (and pays) his share, the
**last purchase absorbs the rounding residual**.

Implementation: the pure function `tools.distribute_rule_of_3` (ratio
= the amount billed by the producer / the calculated sum, then
adjusting the `quantity_invoiced` of each purchase, the last one
taking the remainder). The admin screens `rule_of_3_per_product` and
`rule_of_3_per_customer` build on it.
Tests: `test_rule_of_3.py`, `test_rule_of_3_per_customer.py`.

### Ordered by the piece, billed by weight (PC_KG)

Products sold by the piece but billed by weight (meat: sausages, cordon
bleu...) are **ordered by the piece at a per-kg price**: the screen
shows an **estimate** (pieces x average weight x price/kg,
`order_average_weight`). At closure (`send_to_producer`), the
estimated weight is copied into `quantity_invoiced`. At distribution,
the treasurer replaces it with the **real weight**: the rebilling
follows (pre_save recomputes the price).
Test: `test_adjustments.py` (PcKgWeightBillingTest).

### The deposit (`OrderUnit.DEPOSIT`)

A complete return-tracing mechanism:

- the deposit rides along every purchase of the product
  (`unit_deposit`, VAT-free);
- at closure, **every customer** of the permanence gets one purchase
  line per deposit-type product of the offer (`close_order`, q=1 then
  q=0: prepares the return list);
- the actual returns are adjusted on the same correction screens as
  the rule of three (invoiced quantities).

### The membership fee (`OrderUnit.MEMBERSHIP_FEE`)

A product the group **forces** onto the members who order while their
membership is out of order. At closure (`close_order`): when
`membership_fee > 0` and `membership_fee_duration > 0`
(Configuration) and `customer.membership_fee_valid_until <
permanence_date`, the membership fee product is automatically added to
the member's order and his validity is extended by the configured
duration (minimum: today).
Tests: `test_adjustments.py` (MembershipFeeForcedAtCloseTest),
`test_accounting_chain.py` (the fee is invoiced on the site producer
account).

Within a split (see below), the fee **stays at the parent**: it is a
debt to the group, and the site producer is never paid by the bank.
Test: `test_producer_payment_chain.py`
(MembershipFeeWithinTheSplitTest).

### The site accounts (consumer / producer)

The Repanier site itself owns a consumer account and a producer account
(auto-created by `Customer.get_or_create_group` /
`Producer.get_or_create_group`, flag `represent_this_buyinggroup`):

- the **consumer account** absorbs breakage, unsold goods and
  adjustments, for the good understanding of the group;
- the **producer account** sells the membership fees and any product
  provided for free and resold on the site.

### Invoicing (`Permanence.invoice`)

- Requires a `LATEST_TOTAL` bank anchor; at invoicing, the previous
  one is demoted, a new one is created, and every invoice of the
  permanence is stamped with it (`invoice_sort_order`).
- `calculated_invoiced_balance` = the amount due to the producer
  **as calculated by Repanier**; `to_be_invoiced_balance` = the
  amount **claimed** by the producer (entered by the treasurer, with
  the "to be booked" flag `to_be_paid`).
- The difference between the calculated and the claimed amount -
  **discount granted by the producer to the site, breakage, surplus
  delivered** - books a PROFIT or loss correction for the group
  (`generate_bank_account_movement`), and the producer payment is
  generated for the claimed amount. The customer still pays the
  calculated amount, and the PROFIT correction does not move the bank
  anchor (it is not a real entry).
- Customer payments recorded before the invoicing are attached to the
  permanence and credit the balances before the debit.
- End-to-end locked identities (producers paid square, individual and
  group charging, chained anchor, singleton site accounts):
  `test_accounting_chain.py`.

### Paying the producers one after another (the split)

When the treasurer books only a subset of the producers "to be paid",
the invoicing splits the permanence: the unbooked producers (with
their purchases and the customers involved) move into a **child
permanence** (SEND status, same name, same date, permanence board and
delivery points duplicated), invoiced later, until the last one is
paid (`Permanence.invoice`, `create_child`). Locked rules
(`test_producer_payment_chain.py`):

- the split only happens for a **real subset** (at least one booked
  and at least one not booked): every producer booked -> a single
  invoicing round, no child;
- the **site producer** (its producer invoice is created at every
  permanence by `calculate_order_amount` and carries the group
  deltas) is **excluded** from the split: never paid by the bank,
  never moved, stamped at the current permanence;
- the customer is **debited progressively**: at each round, only the
  purchases of the producers paid in that round; the bank anchors
  chain (each anchor is cumulative, a single live `LATEST_TOTAL`,
  each book stamped with the anchor of its own round);
- the **group invoice follows its members** into the child
  (`is_group` and `customer_charged` preserved), and invoicing the
  child debits the group, never the members;
- between two rounds, the invoiced quantities of the producers still
  in the child stay **adjustable** (breakage, rule of three): the
  customer pays what he received, the producer is paid for what was
  actually delivered;
- a producer may **claim less than calculated** at any round
  (including at the child): the difference books as a PROFIT of the
  site consumer account, attached to the site invoice of that round's
  permanence;
- the split **copies** the customer invoices rather than moving
  them, and invoicing the parent then **deletes the inert shells**:
  a copy without any purchase of its own, without any payment
  attached and with a zero total does not survive the round - a
  fully moved customer leaves no trace at the parent book; a copy
  carrying a payment stays, the money already paid before the
  invoicing remains booked at the parent.
  Test: `PaymentAttachedShellIsKeptTest`.

### Cancellation (`cancel_invoice`)

- only the **latest invoiced book** can be cancelled: the admin
  refuses the request when the live `LATEST_TOTAL` anchor does not
  belong to the permanence ("you must first cancel the invoices of
  ...");
- a chain therefore unrolls in the **reverse order** of the rounds:
  cancelling the child restores that round only (the parent stays
  invoiced, the child can be safely invoiced again, everything back
  square); cancelling child then parent reopens everything (no
  payment left, no anchor row of the chain, the opening anchor live
  again, each book keeping its `canceled_invoice_sort_order` trace);
- cancelling the parent while the child is still at SEND leaves the
  child **intact**: its cargo (producer invoice, purchases, customer
  invoices) does not move back to the parent.
  Tests: `test_producer_payment_chain.py` (CancelTheInvoicedChildTest,
  CancelTheWholeChainFromTheNewestTest,
  CancelTheParentWhileTheChildIsStillOpenTest).

---

*Maintained in parallel with the `repanier/tests/` suite: every
behavior change should come with a test.*
