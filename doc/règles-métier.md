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

### Connexion et protection du compte

- Le membre se connecte **uniquement par son adresse email** : le nom
  long est une identité d'affichage et le nom court un identifiant
  pour les listes de préparation — aucun des deux n'ouvre de session
  (`RepanierAuthBackend.authenticate`). Les comptes sans profil
  client — en pratique les superutilisateurs — gardent une porte
  privée : leur username, un identifiant jamais affiché nulle part,
  pour que leur adresse email publique ne provoque aucun essai de
  connexion.
- Trois mots de passe erronés **verrouillent le compte pendant 15
  minutes** : pendant le verrou, tout mot de passe est refusé — le bon
  compris — et l'écran annonce quand la porte se rouvre. Un bon mot de
  passe saisi avant le verrou remet le compteur d'échecs à zéro ; un
  verrou expiré repart d'un compteur vierge à la tentative suivante.
  Les compteurs laissés au-dessus du seuil par un déploiement
  antérieur verrouillent le compte au prochain échec.
- Un **mail d'avertissement transactionnel** par épisode de verrou
  (envoyé même aux désabonnés, sans pied de désabonnement) invite le
  membre à vérifier son caps lock et son num lock, l'avertit que
  quelqu'un d'autre tente peut-être son compte et le relie au flux de
  réinitialisation du mot de passe. Terminer la réinitialisation
  **lève le verrou immédiatement** — le nouveau mot de passe prouve
  l'identité du demandeur. Le corps du mail nomme le compte
  concerné ; le coordinateur du site reçoit une copie, pour qu'un
  compte dormant demandant de l'aide ou un membre se plaignant arrive
  avec le contexte. Quand le mail échoue lui-même, un rapport
  d'erreur parvient aux admins (`RepanierEmail._send_error`).
- Chaque **connexion d'un superutilateur laisse un court mail aux
  admins** (`ADMIN_EMAIL`) : le site, le compte, l'adresse visible de
  la machine, l'heure. Quelle que soit la porte — le formulaire de
  connexion, /admin/, la porte privée par username — une connexion de
  l'admin est un événement rare et sensible : un mail à une heure
  inhabituelle est une alarme sur laquelle il peut agir. Un problème
  de mail ne bloque jamais la session
  (`repanier.signals.auth.notify_admin_sign_in`).
  Tests : `test_login_view.py` (LoginTemporaryLockTest,
  EmailOnlySignInTest, AdminSignInNotificationTest).

### Le passeport Repanier

Une connexion sur un site de la famille `repanier.be` ouvre les
sessions du membre sur tous les autres sites de la famille où il
possède un compte, sans rien redemander
(`repanier.middleware.repanier_passport_middleware`) :

- la connexion plante un **cookie signé sur le domaine parent**
  `.repanier.be` (HttpOnly, Secure, SameSite Lax, trente jours
  glissants), rafraîchi à chaque visite : une connexion par mois
  couvre toute la famille ;
- le cookie transporte **l'adresse email et le sous-domaine du site
  qui a accueilli le membre en dernier** (gasath pour
  gasath.repanier.be), signés avec
  `REPANIER_SETTINGS_PASSPORT_SIGNING_KEY` — la même valeur sur tous
  les sites de la famille ; aucun compte central n'existe et le
  cookie ne transporte jamais d'autre donnée personnelle que
  l'adresse email de connexion ;
- arrivant sur un autre site, un passeport vérifié ouvre une
  **session locale** pour le compte local de cette adresse email —
  uniquement pour un **membre actif** : le verrou temporaire des
  tentatives échouées ferme le passeport comme il ferme le mot de
  passe, les superutilisateurs, les staffs et les comptes de groupe
  passent par la connexion classique ;
- la même arrivée installe le membre, **par défaut, dans le groupe
  miroir de son site d'origine**, quand ce groupe **accepte
  explicitement les membres du passeport**
  (`accepts_passport_members`, validé par la coordination locale dans
  l'admin des groupes) — une attache gardée de tous côtés :
  uniquement quand la coordination locale n'a jamais placé le
  membre dans un groupe (un groupe déjà posé est définitif),
  uniquement quand un seul groupe local porte le sous-domaine du
  site d'origine (un nom que chaque site de la famille découvre dans
  son navigateur) et accepte les arrivées, jamais pour un membre
  revenant chez lui. Les listes de clients affichent alors
  `[gasath] + nom`, le tableau de livraison suit le groupe ; la
  facturation suit la configuration du groupe lui-même. Décocher le
  drapeau arrête les arrivées futures, sans toucher les membres déjà
  placés. Un compte déjà enregistré sur le site est réparé à la
  prochaine connexion — par passeport ou classique, quand le
  navigateur porte encore un passeport correspondant ;
- la même arrivée peut aussi **inscrire le membre sur le vif** —
  l'inscription familiale. Quand le membre ne possède **pas encore
  de compte** sur le site visité et que ce site tient un groupe
  miroir de son site d'origine qui accepte les membres du passeport,
  le site demande son profil à son site d'origine et crée le compte
  local à partir de lui : nom abrégé et nom étendu, téléphones,
  adresse postale, localité, comptes bancaires, la langue de ses
  mails et la confiance de commande du site d'origine, **copiée
  telle quelle** — un membre que son site d'origine ne laisse pas
  commander ne commande pas non plus sur le site qui l'accueille,
  jusqu'à décision contraire de la coordination locale. Le profil
  ne traverse **qu'entre les serveurs de la famille** — un appel
  signé avec la clé partagée, sur HTTPS, jamais via un navigateur —
  et seulement à l'inscription : le cookie reste aussi sobre
  qu'avant. Le membre atterrit directement dans son groupe miroir,
  ce qui garde son domicile stable, et personne ne se reconnecte
  nulle part : l'appel s'authentifie par la clé, pas par une
  connexion. La clé fait autorité : tout site de la famille qui la
  détient peut interroger, et chaque profil quittant un site laisse
  une trace dans le journal du passeport — qui a demandé le profil
  de qui. Sur ce déploiement, les sites de la famille répondent en
  français (`/fr/passport/profile/`) : le français doit être activé
  sur chaque site de la famille pour que l'inscription les
  atteigne. Tout échec — le site d'origine injoignable, pas de
  groupe miroir, un compte local qui surgit entre-temps — n'inscrit
  personne et ne bloque jamais la page : le membre retombe sur la
  connexion classique. Un nom abrégé déjà pris sur le site visité se
  déplie (`Carine (gasath)`) ; un compte bancaire déjà porté par un
  autre client local reste vide à l'inscription — la garde
  d'intégrité des données du site s'applique au membre arrivant
  exactement comme à tous les autres ; un compte qui existe — dans
  quelque état que ce soit, y compris désactivé ou cassé — n'est
  jamais réécrit, et une inscription cassée (un utilisateur sans
  client) ne se répare qu'arrivant sur un compte actif ;
- le groupe d'un membre du passeport garde ses commandes **seulement
  sur les permanences à points de livraison** : là, il commande
  aux points de livraison de son groupe — ou sans groupe — et une
  permanence qui ne lui en offre aucun lui ferme la porte (« No
  delivery point is open for you »). Sur une permanence **sans
  point de livraison** (`with_delivery_point=False`, la
  distribution centrale), la sélection de livraison est purement et
  simplement sautée : le membre du passeport y commande comme
  n'importe quel membre local, le groupe ne joue aucun rôle. Un
  site qui veut garder ses visiteurs sur leur seule distribution
  ne tient jamais de permanence sans point de livraison ; un site
  qui veut les intégrer au flux central n'en tient que de celles-là ;
- l'origine **ne dérive jamais avec les sauts du membre** : un
  passeport émis alors qu'il appartient à un groupe miroir qui
  l'accepte voyage sous le domicile que ce miroir porte — et quand
  aucun miroir n'existe sur le site visité, sous le domicile du
  passeport avec lequel il est arrivé. Un membre de gasath qui
  rebondit de site en site continue de voyager comme gasath et ne
  devient jamais, à force de visites, membre de l'endroit qu'il a
  simplement visité ;
- la routine de famille — l'**audit du passeport** : un cron
  nocturne (`./manage.py passport_audit`) demande à chaque site
  d'origine, serveur à serveur et signé avec la clé de famille, si
  chaque membre placé ici lui appartient toujours. **Lecture seule,
  pour toujours** : les constats — « son site d'origine ne le
  connaît plus », « son site d'origine n'a pas répondu » — arrivent
  à la coordination par mail, et la coordination décide ; l'audit
  ne touche jamais un compte. Le silence n'est jamais un départ :
  une panne réseau, un retard de déploiement et une mauvaise clé
  répondent le même None ;
- les sites vivant sur leur propre domaine (colibera.be,
  commande.lebuisson.be, commande.coopeco-supermarche.be) ne portent
  pas de passeport : leurs membres se connectent site par site ;
- quitter un site (déconnexion) supprime le cookie de famille : le
  membre quitte tous les sites à la fois. La clé de signature vient
  de `./manage.py generate_passport_signing_key` — la même valeur
  dans l'ini de chaque site de la famille, vide sur les sites à
  domaine propre. L'endpoint profil d'un site vit sous
  `/fr/passport/profile/` et la routine interroge sous
  `/fr/passport/verify/` : seul un site qui tient la clé peut
  interroger, tout ce qu'un endpoint refuse répond le même 404
  silencieux (un GET répond 405 — les endpoints ne parlent qu'en
  POST) ;
- le passeport couvre aussi un membre **déconnecté partout** : il
  lui reste son mot de passe sur son site d'origine, et la porte de
  login demande à ce site de se porter garant pour lui
  (`/fr/passport/request/`, `/fr/passport/login/`,
  `/fr/passport/arrive/`). Sur le site cible, le membre choisit son
  site d'origine parmi les groupes miroirs qui acceptent les
  arrivées — l'écran de connexion ne propose la porte qu'alors, et
  seulement sur la famille repanier.be. Le navigateur atterrit sur
  la page de connexion du site d'origine avec une URL de retour de
  la famille ; le site d'origine le connecte — ou réutilise la
  session qu'il y possède encore — et tamponne un **jeton signé
  d'une minute** (l'e-mail authentifié et son propre sous-domaine,
  sel dédié `repanier/1905/passport-login`). Le navigateur revient,
  le site cible vérifie le jeton avec la clé de la famille et ouvre
  la porte exactement comme une arrivée de passeport : la session
  locale d'un compte existant — le verrou des tentatives échouées
  s'applique à la danse comme il s'applique au mot de passe — ou
  l'inscription de la famille. **Le mot de passe ne quitte jamais
  le site d'origine et ne circule jamais dans un navigateur** ; une
  cible de retour hors de la famille ne mène nulle part, un jeton
  d'un autre sel ou d'un autre site n'ouvre rien, rentrer chez soi
  refuse la danse (le cookie seul ouvre la porte), et tout refus
  reste silencieux : le membre retombe sur la connexion classique.
  Tests : `test_repanier_passport.py`, `test_passport_enrolment.py`,
  `test_passport_verify.py`, `test_passport_login.py`,
  `test_customer_language.py` (SessionLanguageCookieTest).

- la langue du membre **ne circule jamais entre les sites** : rien
  ne les traverse pour elle. Chaque ouverture de session de membre -
  une connexion à la main, une arrivée de passeport, la porte de
  login - plante son `Customer.language` comme un cookie de langue
  **lié à ce seul site**, quand ce site pratique cette langue (« fr »
  sur un site fr, « nl » sur un site fr-nl). Une langue que le site
  ne pratique ne traverse jamais vers le cookie - le CMS continue de
  planter la langue des pages qu'il rend, et le repli du site
  s'applique. Un membre inscrit par l'inscription de la famille
  démarre avec la langue copiée de son site d'origine, et la change
  site par site sur son propre écran.
  Tests : `test_repanier_passport.py`, `test_passport_enrolment.py`,
  `test_passport_verify.py`, `test_passport_login.py`,
  `test_customer_language.py` (SessionLanguageCookieTest).

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

Si une permanence a une date de clôture automatique, le cron la ferme
et transmet les commandes à partir de l’heure de clôture configurée pour
le site. Laisser la date vide pour clôturer la permanence manuellement.

### Ajustements avant facturation

Pour une permanence réelle en `SEND`, le panneau de clôture donne accès
aux fiches des produits de la livraison. Une modification de prix y concerne
la livraison ; la case explicite de mise à jour du catalogue rend également
le prix durable. Les achats concernés et les totaux de leurs factures sont
recalculés. La fiche catalogue séparée modifie le produit pour l'avenir.

On peut attribuer à un membre un article de la livraison qui n'avait pas été
commandé ou un article actif du catalogue absent de la livraison, si son
fournisseur participe à la permanence. Les paniers et articles spéciaux
(consignes et cotisations) ne sont pas ajoutés par cette dernière voie.
L'achat est relié aux trois factures et conserve une quantité commandée nulle ;
les erreurs annulent la transaction. Aucun paiement ni mouvement bancaire
n'est créé par cet ajustement.

### Validation tacite des remises aux groupes

`python manage.py auto_validate_group_deliveries --dry-run` affiche les
candidats et les dossiers en attente ; sans `--dry-run`, seuls les états
de préparation éligibles sont validés. `--days` fixe le délai, à deux
jours par défaut, après la date de permanence **et** la remise enregistrée.
La permanence doit être ouverte à la préparation, en statut `SEND`, et
ne pas être une démonstration. Un conflit, un rejet ou tout événement
non appliqué bloque la permanence.

Une ligne doit avoir une remise et une réception enregistrées, sans
anomalie de colis ni substitution, et ses quantités commandée,
préparée, reçue et facturée doivent concorder. Les quantités relevées
dans les événements de préparation et de réception doivent aussi être
lisibles et conformes. Une ambiguïté ou un écart d'une ligne bloque
toutes les lignes en remise de ce point de livraison ; le dossier reste en attente pour
revue humaine ; aucune écriture bancaire ni modification de solde n'est
créée. Cette règle conservatrice n'impute pas les écarts collectifs.

Les exemples d'exploitation des commandes et timers, ainsi que l'utilitaire
de proposition d'alias en lecture seule, sont décrits dans
`doc/exploitation-batch.md`.

Sur une ligne groupée standard, le bouton OK enregistre pour chaque achat
une préparation si nécessaire, puis une réception et une remise au groupe,
dans cet ordre. Après synchronisation, l'état est « remis au groupe »,
et non « validé » : la validation tacite intervient ultérieurement.
Une remise en conflit reste bloquée pour examen par le responsable.

Un arrivage incertain lié à une distribution est signalé au panier et
en préparation ; il ne rend pas les créneaux indisponibles et ne valide
pas à lui seul les lignes de préparation.
La distribution est actuellement liée à une seule `Offer` : le signal
ne détaille pas les arrivages par producteur ni par article lorsque la
permanence comprend plusieurs offres fournisseur. Les offres non liées
ne sont pas prises en compte ; cette granularité nécessite une évolution
du modèle avant de pouvoir être exploitée.

### Créneaux de retrait et limites hors ligne

Sur le panier d'une commande ouverte, le membre peut enregistrer un
créneau de la distribution liée à sa permanence. Un créneau unique est
attribué automatiquement lors de l'initialisation ; avec plusieurs
créneaux, aucun choix n'est imposé. Changer de créneau annule une
confirmation déjà envoyée : le membre doit confirmer à nouveau. Le
même créneau ne l'annule pas. Les commandes fermées ou facturées ne
permettent plus de modifier le créneau. Aucun créneau n'est requis
pour les permanences qui n'en possèdent pas.

La validation tacite ne voit que les événements reçus par le serveur :
un écart encore en attente sur un GSM hors ligne ne peut pas bloquer
la commande. Synchroniser les appareils et traiter les conflits avant
de l'exécuter ; le délai ne garantit pas que tous les GSM ont été
reconnectés.

### La langue des mails aux membres

Le site est multilingue (les langues vivent dans l'ini,
`DJANGO_SETTINGS_LANGUAGE`), mais le processus d'envoi tourne dans la
langue du site : sans précaution, chaque membre reçoit ses mails en
français quel que soit son profil. La confirmation de commande —
planifiée, confirmée à la main ou annulée — est construite et envoyée
dans **la langue du membre** (`Customer.language`) : sujet, corps et
pièce jointe (`in_customer_language`, `export_order_2_1_customer`).
La langue se règle sur l'écran consommateur de l'admin, à côté de
l'abonnement aux mails — la coordination peut la voir et la corriger
— **et sur l'écran « Mes données » du membre, qui la choisit
lui-même**. Sur cet écran, l'**adresse email de connexion s'affiche
pour mémoire, en lecture seule** : un membre qui la toucherait
pourrait se verrouiller hors de son propre compte, elle ne bouge
donc que de la main de la coordination.
Test : `test_customer_language.py`.

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

**Symétrie des flux d'annulation.** La clôture mémorise la date de
validité antérieure du membre sur sa facture client
(`CustomerInvoice.membership_fee_valid_until_save`). Tout ce qui défait
la permanence restaure cette date antérieure : l'annulation de la
livraison (`cancel_delivery`, SEND -> CANCELLED) et l'annulation de la
facturation (`cancel_invoice`, la réversion compta). Tout ce qui
ré-applique la permanence re-prolonge la validité depuis ce même
snapshot : la restauration d'une livraison annulée (`restore_delivery`)
et la re-facturation après une facturation annulée. La restauration ne
raccourcit jamais une date prolongée ensuite par une autre permanence
(la mise à jour ne s'applique que si la date courante est encore celle
calculée par cette permanence).
Tests : `test_membership_fee_cancel.py`.

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
- Après le rattachement des mouvements, la facturation **supprime les
  livres inertes à total nul** : coquilles de la scission, groupes de
  points de livraison sans aucune facturation et leurs membres qui
  n'ont rien commandé, et les livres des comptes du site eux-mêmes —
  le livre consommateur du site tant qu'aucun profit, taxe ou
  ajustement n'y a rattaché de mouvement, le livre producteur du site
  tant qu'il ne porte ni les deltas du groupe ni les produits vendus
  par le site. Un livre portant un achat ou un paiement ne peut
  jamais être supprimé (PROTECT).
  Tests : `PaymentAttachedShellIsKeptTest`, `NothingBilledGroupIsRemovedTest`.
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
- la scission **copie** les factures clients plutôt qu'elle ne les
  déplace, puis la facturation du parent **supprime les coquilles
  inertes** : une copie sans aucun achat propre, sans paiement
  rattaché et à total nul ne survit pas au tour — un client
  entièrement déplacé ne laisse aucune trace dans le livre du
  parent ; une copie portant un paiement survit, l'argent déjà payé
  avant la facturation reste comptabilisé au parent.
  Test : `PaymentAttachedShellIsKeptTest`.

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

### L'audit comptable (`audit_accounting`)

- une commande en lecture seule rejoue tout l'historique d'un site et
  compare ce que l'algèbre de la facturation recalcule avec ce que
  la base stocke (`./manage.py audit_accounting`, avec
  `--permanence` et `--customer` pour cibler) ;
- six classes d'invariants : les soldes clients (solde initial +
  banque attachée − livres facturés), les soldes producteurs (idem,
  moins les corrections PROFIT, qui doivent aussi correspondre à ce
  que la facturation a réellement booké sur le compte consommateur
  du site), les totaux des livres recalculés depuis les achats
  (transport et arrondi belge compris), les totaux des sessions
  (facturé aux clients == booké aux producteurs), les tampons de
  clôture d'une session (statut et ancre bancaire sur chaque livre
  et chaque achat), et la chaîne des ancres bancaires (une seule
  LATEST_TOTAL, chaque ancre équilibre les mouvements attachés
  pendant sa session, aucun paiement plus ancien que la dernière
  ancre ne reste détaché) ;
- l'audit **ne répare jamais rien** : chaque constat porte le
  rejeu, les valeurs stockées et une réparation suggérée ; le code
  de sortie vaut 1 exactement quand un constat existe. Un
  `previous_balance` faux est hérité par le rejeu (angle mort
  documenté), la dérive qu'il introduit à sa propre session est
  néanmoins détectée.
  Tests : `test_audit_accounting.py` (le journal sain reste muet,
  une rayure par classe est attrapée, et chaque audit prouve son
  caractère lecture seule par un instantané avant/après).

---

*Document entretenu en parallèle de la suite de tests `repanier/tests/` ;
toute évolution du comportement devrait aller de pair avec un test.*
