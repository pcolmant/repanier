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

### Sign in and account protection

- Members sign in **with their e-mail address only**: the long name
  is a display identity and the short name an identifier for the
  preparation lists - neither of them ever opens a session
  (`RepanierAuthBackend.authenticate`). The accounts without a
  customer profile - in practice the superusers - keep one private
  door: their username, an identifier never displayed anywhere,
  so their public e-mail address provokes no guessing.
- Three failed passwords **lock the account for 15 minutes**:
  during the lock, every password bounces - the correct one included -
  and the screen announces when the door reopens. A correct password
  entered before the lock resets the failed-attempt counter; an expired
  lock starts a fresh count on the next try. Counters left above the
  threshold by an earlier deployment lock the account on the next
  failed attempt.
- One **transactional warning mail** per lock episode (sent even to
  unsubscribed members, without the unsubscribe footer) invites the
  member to check his caps lock and his num lock, warns him that
  somebody else may be trying his account, and links to the password
  reset flow. Completing the reset **lifts the lock immediately** -
  the new password proves the identity of the asker. The body of the
  mail names the concerned account; the
  site coordinator receives a copy, so a dormant account asking for
  help or a complaining member arrives with the context. When the mail
  itself fails, an error report reaches the admins
  (`RepanierEmail._send_error`).
- Every **superuser sign in leaves a short mail to the admins**
  (`ADMIN_EMAIL`): the site, the account, the visible address of the
  machine, the moment. Whatever the door - the sign in form, /admin/,
  the private username door - a connection of the admin is a rare and
  sensitive event: a mail at an odd hour is an alarm he can act on.
  A mail problem never blocks the session
  (`repanier.signals.auth.notify_admin_sign_in`).
  Tests: `test_login_view.py` (LoginTemporaryLockTest,
  EmailOnlySignInTest, AdminSignInNotificationTest).

### The Repanier passport

One sign in on a site of the `repanier.be` family opens the member
sessions on every other site of the family where his account exists,
without asking anything again (`repanier.middleware.repanier_passport_middleware`):

- the sign in plants a **signed cookie on the parent domain**
  `.repanier.be` (HttpOnly, Secure, SameSite Lax, a sliding thirty
  days), refreshed on every visit: one sign in a month covers the
  whole family;
- the cookie carries the **e-mail address and the subdomain of the
  site which last welcomed the member** (gasath for
  gasath.repanier.be), signed with
  `REPANIER_SETTINGS_PASSPORT_SIGNING_KEY` - the same value in every
  site of the family; no central account exists and the cookie
  itself never carries any personal data beyond the sign in e-mail;
- arriving on another site, a verified passport opens a **local
  session** for the local account of that e-mail address - only for
  an **active member**: the temporary lock of the failed attempts
  closes the passport as it closes the password, the superusers, the
  staff and the group accounts go through the classical sign in;
- the same arrival places the member, **by default, in the mirror
  group of his home site**, when that group **explicitly accepts the
  passport members** (`accepts_passport_members`, validated by the
  local coordination in the group admin) - an attach guarded on every
  side: only when the local coordination has never placed the member
  in any group (a group already set is final), only when exactly one
  local group wears the subdomain of the home site (a name any site
  of the family can discover in its browser) and accepts the
  arrivals, never for a member coming back home. The customer lists
  then show `[gasath] + name` and the delivery board follows the
  group; the invoicing follows the configuration of the group
  itself. Turning the flag off stops the future arrivals, without
  touching the members already placed. An account already registered
  on the site is repaired at the next sign in - by passport or by
  hand, when the browser still carries a matching passport;
- the same arrival may also **register the member on the spot** -
  the family enrolment. When the member owns **no account yet** on
  the visited site and that site runs a mirror group of his home
  which accepts the passport members, the site asks his home site for
  his profile and creates the local account from it: short and long
  names, phones, postal address, city, bank accounts, the language
  of his mails and the may-order trust of the home site, **copied
  as is** - a member the home site does not let order does not
  order either on the site which welcomes him, until the local
  coordination decides otherwise. The profile crosses **only
  between the servers of the family** - a call signed with the
  shared key, over HTTPS, never through a browser - at the
  enrolment only: the cookie stays as small as before. The member
  lands directly in his mirror group, which keeps his home stable,
  and nothing reconnects anybody anywhere: the call authenticates
  with the key, not with a sign in. The key is the authority: every
  site of the family holding it may ask, and every profile leaving
  a site leaves a trail in the passport log - who asked for whose
  profile. On this deployment the family sites answer in French
  (`/fr/passport/profile/`): the French language must be enabled on
  every site of the family for the enrolment to reach them. Any
  failure - the home site unreachable, no mirror group, a local
  account appearing in between - enrols nobody and never blocks the
  page: the member falls back on the classical sign in. A short
  name already taken on the visited site unfolds (`Carine
  (gasath)`); a bank account already carried by another local
  customer is left empty by the enrolment - the data integrity
  guard of the site applies to the arriving member exactly as to
  everybody else; an account which exists - in any state,
  including a disabled or broken one - is never written over, and a
  broken enrolment (a user without a customer) is repaired on the
  next arrival of an active account;
- the group of a passport member guards his orders **only on the
  permanences with delivery points**: there he orders at the
  delivery points of his group - or of no group - and a permanence
  which offers him none closes the door on him (`No delivery point
  is open for you`). On a permanence **without delivery point**
  (`with_delivery_point=False`, the central distribution), the
  delivery selection is skipped entirely: the passport member
  orders there like any local member, the group plays no role. A
  site which wants its visiting members to stay on their own
  distribution never runs a permanence without delivery points; a
  site which wants them in the central flow runs only those;
- the origin **never drifts with the hops of the member**: a passport
  issued while he belongs to a mirror group which accepts him
  travels under the home that mirror wears - and when no mirror
  exists on the visited site, under the home of the passport he
  arrived with. A member of gasath bouncing from site to site keeps
  travelling as gasath and never becomes, by sheer visiting, a
  member of the place he merely visited;
- the family routine - the **passport audit**: a nightly cron
  (`./manage.py passport_audit`) asks every home site, server to
  server and signed with the family key, whether each member
  placed here still belongs to it. **Read only, forever**: the
  findings - "his home site does not know him anymore", "his home
  site stayed silent" - reach the coordination by mail, and the
  coordination decides; the audit never touches an account.
  Silence is never a departure: a network failure, a deployment
  lag and a wrong key all answer the same None;
- the sites living on their own domain (colibera.be,
  commande.lebuisson.be, commande.coopeco-supermarche.be) carry no
  passport: their members sign in on each site;
- leaving one site (logout) deletes the family cookie: the member
  leaves every site at once. The signing key comes from
  `./manage.py generate_passport_signing_key` - the same value in
  every family site ini, empty on the own-domain sites.
  The profile endpoint of a site lives at `/fr/passport/profile/`
  and the routine asks at `/fr/passport/verify/`: only a site
  holding the key can ask, everything either endpoint refuses
  answers the same silent 404 (a GET answers 405 - the endpoints
  speak POST only).
- the passport also covers a member **logged out everywhere**: he
  still owns his password on his home site, and the login door asks
  that home site to vouch for him (`/fr/passport/request/`,
  `/fr/passport/login/`, `/fr/passport/arrive/`). On the target site,
  the member picks his home among the mirror groups which accept
  the arrivals - the login screen offers the door only then, only
  on the repanier.be family. The browser lands on the home site
  login page with a family return URL; the home site signs him in -
  or reuses the session he still owns there - and stamps a **one
  minute signed token** (his authenticated e-mail and its own
  subdomain, own salt `repanier/1905/passport-login`). The browser
  returns, the target verifies the token with the shared key and
  opens the door exactly like a passport arrival: the local session
  of an existing account - the login lock of the failed attempts
  applies to the dance as it applies to the password - or the family
  enrolment. **The password never leaves the home site and never
  travels through a browser**; a return target outside the family
  goes nowhere, a token of another salt or of another site opens
  nothing, coming home refuses the dance (the cookie alone opens
  the door), and every refusal stays silent: the member falls back
  on the classical sign in.
- the passport login door never travels the member's language:
  nothing crosses the sites for it. Every opening of a member
  session - a sign in by hand, a passport arrival, the login door -
  plants his `Customer.language` as a **host only** language cookie,
  when this site runs that language ("fr" on a fr site, "nl" on a
  fr-nl site). A language the site does not run never crosses into
  the cookie - the CMS keeps planting the language of the pages it
  renders, and the fallback of the site applies. A member registered
  by the family enrolment starts with the language copied from his
  home site, and changes it per site on his own screen.
  Tests: `test_repanier_passport.py`, `test_passport_enrolment.py`,
  `test_passport_verify.py`, `test_passport_login.py`,
  `test_customer_language.py` (SessionLanguageCookieTest).

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

### The language of the member mails

The site is multilingual (the languages live in the ini,
`DJANGO_SETTINGS_LANGUAGE`), but the sending process runs in the
language of the site: without care, every member receives his mails
in French whatever his profile says. The order confirmation -
scheduled, confirmed by hand or cancelled - is built and sent under
the **language of the member** (`Customer.language`): subject, body
and attachment (`in_customer_language`, `export_order_2_1_customer`).
The language sits on the customer screen of the admin, next to the
subscription to the mails - the coordination can see it and correct
it - **and on the "My data" screen of the member, who chooses it
himself**. On that screen the **sign in e-mail shows for memory
only**, read-only: a member touching it could lock himself out of
his own account, so it moves only by the hand of the coordination.
Test: `test_customer_language.py`.

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

**Symmetry of the cancellation flows.** The closure snapshots the member's
previous validity date onto his customer invoice
(`CustomerInvoice.membership_fee_valid_until_save`). Whatever unwinds
the permanence restores that previous date: cancelling the delivery
(`cancel_delivery`, SEND -> CANCELLED) or cancelling the invoicing
(`cancel_invoice`, the accounting reversal). Whatever re-applies the
permanence re-extends the validity from the same snapshot: restoring a
cancelled delivery (`restore_delivery`) or invoicing again after a
cancelled invoicing. The restore never shortens a date another
permanence extended afterwards (the update only fires when the current
date is still the one this permanence computed).
Tests: `test_membership_fee_cancel.py`.

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
- After the movements attach, the invoicing **deletes the inert
  zero-total books**: the split shells, the nothing-billed delivery
  point groups and their ordering-but-empty members, and the books of
  the site accounts themselves - the site consumer book when no
  profit, tax or adjustment attached a bank movement to it, the site
  producer book when it carries neither the group deltas nor the
  products sold by the site. A book carrying a purchase or a payment
  can never be deleted (PROTECT).
  Tests: `PaymentAttachedShellIsKeptTest`, `NothingBilledGroupIsRemovedTest`.
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

### The accounting audit (`audit_accounting`)

- a read-only command replays the whole history of a site and
  compares what the algebra of the invoicing recomputes with what
  the database stores (`./manage.py audit_accounting`,
  `--permanence` and `--customer` to scope it);
- six classes of invariants: the customer balances (initial balance
  + bank attached - invoiced books), the producer balances (the same,
  minus the PROFIT corrections, which must also match what the
  invoicing really booked on the site consumer account), the book
  totals recomputed from the purchases (transport and Belgian
  rounding included), the round totals (charged to the customers ==
  booked on the producers), the closure stamps of a round (status and
  bank anchor on every book and purchase), and the bank anchor chain
  (one LATEST_TOTAL, each anchor nets the movements attached during
  its round, no payment older than the latest anchor left
  unattached);
- the audit **never repairs anything**: every finding carries the
  replay, the stored values and a suggested repair; the exit code is
  1 exactly when findings exist. A wrong `previous_balance` is
  inherited by the replay (documented blind spot), the drift it
  introduces at its own round is still caught.
  Tests: `test_audit_accounting.py` (the clean journal stays silent,
  one scratch per class is caught, and each audit is proven read
  only by a before/after snapshot).

---

*Maintained in parallel with the `repanier/tests/` suite: every
behavior change should come with a test.*
