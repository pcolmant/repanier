# Règles de gestion Repanier (business rules)

> **Version française.** La version anglaise de référence est
> [`business-rules.md`](business-rules.md) : en cas d'écart, c'est
> elle qui fait foi. Les deux fichiers sont mis à jour dans la même PR.

Ce document recense les règles de gestion identifiées dans le code et
verrouillées (progressivement) par la suite de tests (`repanier/tests/`).
Les références de code indiquent où chaque règle vit ; les références de
tests indiquent où elle est vérifiée.

---

## Partie 1 — Règles classiques

### Chaîne d'achat

Un achat (Purchase) relie **une facture client** (CustomerInvoice), **une
facture producteur** (ProducerInvoice) et **une facture
client-producteur** (CustomerProducerInvoice). Les trois sont créées
automatiquement au premier achat de la paire (client, offre)
(`Purchase.save`, signals/purchase.py).

Le signal `pre_save` de Purchase recalcule les prix à chaque
enregistrement : `(prix unitaire client + consigne) x quantité` pour le
client, `(prix unitaire producteur + consigne) x quantité` pour le
producteur, TVA des deux côtés, incrément des factures par delta.
Test : `test_purchase_flow.py`.

### Prix et TVA

- Le prix client est **toujours dérivé** du prix producteur :
  `prix client = prix producteur x coefficient` (Producer.
  price_list_multiplier, appliqué dans `Item.recalculate_prices`).
  Le prix saisi sur le produit n'est jamais la référence.
- Le producteur communique ses prix **HTVA ou TVAC**
  (`Producer.producer_price_are_wo_vat`). Les formules asymétriques de
  recalcul (viande TVA du prix HT vs extraction de la TVA du prix TTC)
  sont dans `Item.recalculate_prices`.
- TVA par paliers (`Vat` : 0 %, 2,5 %, 3,8 %, 6 %, 8 %, 12 %, 21 %),
  quantifiée à 4 décimales ; les prix le sont à 2 décimales.
- **Aucune TVA n'est appliquée sur les consignes** : la consigne est
  additionnée au prix unitaire après calcul de la TVA.
  Tests : `test_vat_matrix.py`.

### Frais de livraison (transport)

Si la commande du client est inférieure au seuil de franchise
(`min_transport`), des frais s'appliquent, plafonnés à la fois par le
montant manquant pour atteindre le seuil et par le montant des frais
(`CustomerInvoice.calculate_order_transport`). Pas de frais sur une
commande vide ; pas de frais pour un membre de groupe (c'est le payeur
du groupe qui les porte). Tests : `test_invoice_calculation.py`.

### Arrondi espèces (Belgique)

Quand `REPANIER_SETTINGS_ROUND_INVOICES` est actif, le total final est
arrondi au multiple de 0,05 € le plus proche (`tools.round_gov_be`,
règle officielle) ; le delta est reporté sur `delta_price_with_tax`.
Tests : `test_tools.py`, `test_invoice_calculation.py`.

### Stock

Une commande ne peut pas dépasser le stock disponible moins ce qui est
déjà réservé (offer_item.get_q_alert) ; les diminutions sous le stock
déjà vendu sont refusées. Test : `test_purchase_flow.py`.

### Cycle d'une permanence

`PLANNED → (WAIT_FOR_OPEN) → OPENED → (WAIT_FOR_CLOSED) → CLOSED
→ (WAIT_FOR_SEND) → SEND → INVOICED → ARCHIVED`
(`Permanence.set_status`, `task_order.open_order`, `close_order`).
`highest_status` ne redescend jamais : il mémorise le plus haut état
atteint. Toute transition incohérente lève `ValueError`.
Une annulation de facturation (`cancel_invoice`) ramène la permanence
de INVOICED à SEND (voir « Annulation » en partie 2).
Tests : `test_status_flow.py`, `test_order_journey.py`.

### Clôture automatique

Une permanence marquée `automatically_closed` est fermée (et les
commandes transmises) par le cron sans intervention.

---

## Partie 2 — Règles signatures (le cœur de Repanier)

### Le groupe et son point de livraison

Un groupe est un client (`Customer.is_group`) **lié à un point de
livraison** (`LUT_DeliveryPoint.group`). Les membres du groupe
(`Customer.group`) reçoivent le board de livraison du groupe **par
défaut** à la commande : ce point route à la fois la logistique ET la
facturation (`CustomerInvoice.set_order_delivery`).

Deux modèles de facturation :

- **paiement individuel** : `customer_charged == customer` ;
- **facturation au groupe** : les membres commandent individuellement,
  mais chaque facture membre pointe vers le groupe
  (`customer_charged == groupe`), et la facture du groupe **agrège**
  les achats qui lui sont imputés. Après comptabilisation : le solde du
  groupe est débité, **les soldes des membres ne bougent pas**.
  Tests : `test_invoicing.py` (GroupInvoicingTest).

### Clôture point par point

Une permanence avec points de livraison peut être clôturée **pour un ou
plusieurs points seulement** (`close_order(everything=False,
deliveries_id=[...])`) : les clients du point clôturé sont bloqués, la
permanence **reste ouverte** pour les autres points qui continuent
d'accepter des commandes. La clôture complète (tous les points) fait
passer la permanence à SEND.
Test : `test_invoicing.py` (PartialDeliveryPointClosureTest).

### La règle de 3

Répartir un produit livré entre les consommateurs **au pro rata** pour
que le total facturé aux consommateurs corresponde au centime au
montant facturé par le producteur. Exemple : 10 kg commandés, le
producteur livre 10,5 kg mais en facture 10 — chacun reçoit (et paie)
sa part, le **dernier achat absorbe le résidu d'arrondi**.

Implémentation : fonction pure `tools.distribute_rule_of_3`
(ratio = montant facturé par le producteur / somme calculée, puis
ajustement des `quantity_invoiced`, le dernier achat prenant le
reste). Les écrans admin `rule_of_3_per_product` et
`rule_of_3_per_customer` s'appuient dessus.
Tests : `test_rule_of_3.py`, `test_rule_of_3_per_customer.py`.

### À la pièce, facturé au poids (PC_KG)

Les produits vendus à la pièce mais facturés au poids (viande :
saucisses, cordons bleus...) se commandent **à la pièce avec un prix
au kg** : l'écran annonce une **estimation**
(pièces x poids moyen x prix/kg, `order_average_weight`). À la clôture
(`send_to_producer`), le poids estimé est copié dans
`quantity_invoiced`. À la distribution, le trésorier remplace par le
**poids réel** : la refacturation suit (pre_save recalcule le prix).
Test : `test_adjustments.py` (PcKgWeightBillingTest).

### La consigne (`OrderUnit.DEPOSIT`)

Mécanisme complet de traçabilité des retours :

- la consigne accompagne chaque achat du produit concerné
  (`unit_deposit`, sans TVA) ;
- à la clôture, **chaque client** de la permanence reçoit une ligne
  d'achat pour chaque produit de type consigne de l'offre
  (`close_order`, q=1 puis q=0 : prépare la liste des retours) ;
- les retours réels sont ajustés sur les mêmes écrans de correction
  que la règle de 3 (quantités facturées).

### La cotisation (`OrderUnit.MEMBERSHIP_FEE`)

Un produit que le groupe **force** à la vente auprès des membres qui
passent commande sans être en règle de cotisation. À la clôture
(`close_order`) : si `membership_fee > 0` et
`membership_fee_duration > 0` (Configuration) et que
`customer.membership_fee_valid_until < permanence_date`, le produit
cotisation est ajouté automatiquement à la commande du membre et sa
validité est prolongée de la durée configurée (minimum : aujourd'hui).
Tests : `test_adjustments.py` (MembershipFeeForcedAtCloseTest),
`test_accounting_chain.py` (cotisation sur le compte producteur du
site).

Dans une scission (voir plus bas), la cotisation **reste au parent** :
c'est une dette envers le groupe, et le producteur du site n'est jamais
payé par la banque.
Test : `test_producer_payment_chain.py` (MembershipFeeWithinTheSplitTest).

### Les comptes du site (consommateur / producteur)

Le site Repanier lui-même possède un compte consommateur et un compte
producteur (auto-créés par `Customer.get_or_create_group` /
`Producer.get_or_create_group`, flag `represent_this_buyinggroup`) :

- le **compte consommateur** prend en charge casses, invendus et
  ajustements pour la bonne entente du groupe ;
- le **compte producteur** vend les cotisations et tout produit mis
  gratuitement à disposition et revendu.

### Comptabilisation (`Permanence.invoice`)

- Exige une ancre bancaire `LATEST_TOTAL` ; à la facturation, l'ancienne
  est rétrogradée, une nouvelle est créée et toutes les factures de la
  permanence sont estampillées (`invoice_sort_order`).
- `calculated_invoiced_balance` = montant dû au producteur **calculé
  par Repanier** ; `to_be_invoiced_balance` = montant **réclamé** par
  le producteur (saisi par le trésorier, avec le drapeau `to_be_paid`
  « à booker »).
- La différence entre le calculé et le réclamé — **remise du
  producteur au site, casse, surplus livré** — produit une ligne de
  correction PROFIT ou perte pour le groupe
  (`generate_bank_account_movement`), et le paiement du producteur
  est généré pour le montant réclamé. Le client paie quand même le
  montant calculé, et la correction PROFIT ne bouge pas l'ancre
  bancaire (ce n'est pas une entrée réelle).
- Les paiements clients saisis avant la facturation sont rattachés à
  la permanence et viennent créditer les soldes avant le débit.
- Identités verrouillées bout en bout (produits payés carré, payer
  individuellement et par groupe, ancre chaînée, comptes du site
  singletons) : `test_accounting_chain.py`.

### Paiement des producteurs l'un après l'autre (la scission)

Quand le trésorier ne coche qu'une partie des producteurs « à payer »,
la facturation scinde la permanence : les producteurs non cochés (avec
leurs achats et les clients concernés) déménagent dans une
**permanence enfant** (statut SEND, même nom, même date, tableau de
permanence et points de livraison dupliqués) qui sera facturée plus
tard, jusqu'au paiement du dernier (`Permanence.invoice`,
`create_child`). Règles verrouillées
(`test_producer_payment_chain.py`) :

- la scission ne s'applique que si un **vrai sous-ensemble** est
  sélectionné (au moins un coché et au moins un non coché) : tout le
  monde coché → facturation en un seul tour, sans enfant ;
- le **producteur du site** (sa facture est créée à chaque permanence
  par `calculate_order_amount` et porte les deltas du groupe) est
  **exclu** de la scission : jamais payé par la banque, jamais
  déplacé, estampillé à la permanence courante ;
- le client est **débité progressivement** : à chaque tour, seulement
  les achats des producteurs payés à ce tour-là ; les ancres bancaires
  s'enchaînent (chaque ancre est cumulative, un seul `LATEST_TOTAL`
  vivant, chaque livre estampillé avec l'ancre de son tour) ;
- la **facture du groupe suit ses membres** dans l'enfant
  (`is_group` et `customer_charged` préservés) et la facturation de
  l'enfant débite le groupe, jamais les membres ;
- entre deux tours, les quantités facturées des producteurs encore
  dans l'enfant restent **ajustables** (casse, règle de 3) : le client
  paie ce qu'il a reçu, le producteur est payé pour le livré réel ;
- un producteur peut **réclamer moins que le calculé** à n'importe
  quel tour (y compris à l'enfant) : la différence devient un PROFIT
  du compte consommateur du site, attaché à la facture site de la
  permanence du tour ;
- comportement documenté : la scission **copie** les factures clients
  plutôt qu'elle ne les déplace — un client entièrement déplacé
  laisse une coquille inerte à 0,00 dans le livre du parent (sans
  achat, sans effet de solde, jamais débitée).

### Annulation (`cancel_invoice`)

- seul le **dernier livre facturé** peut être annulé : l'admin refuse
  la demande si l'ancre `LATEST_TOTAL` vivante n'appartient pas à la
  permanence concernée (« annulez d'abord les factures de … ») ;
- une chaîne se déroule donc **en ordre inverse** des tours : annuler
  l'enfant restaure seulement son tour (parent toujours facturé,
  ré-facturation de l'enfant possible ensuite, tout redevient carré) ;
  annuler enfant puis parent rouvre tout (plus aucun paiement, plus
  aucune rangée d'ancre de la chaîne, l'ancre d'ouverture vivante à
  nouveau, chaque livre gardant sa trace `canceled_invoice_sort_order`) ;
- annuler le parent alors que l'enfant est encore à SEND laisse
  l'enfant **intact** : sa cargaison (facture producteur, achats,
  factures clients) ne revient pas au parent.
  Tests : `test_producer_payment_chain.py` (CancelTheInvoicedChildTest,
  CancelTheWholeChainFromTheNewestTest,
  CancelTheParentWhileTheChildIsStillOpenTest).

---

*Document entretenu en parallèle de la suite de tests `repanier/tests/` ;
toute évolution du comportement devrait aller de pair avec un test.*
