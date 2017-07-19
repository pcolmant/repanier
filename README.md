Repanier
========

Collective buying group management web site using Django CMS 3.4.1 / Bootstrap 3.

- https://repanier.be/fr/documentation/survol/

- https://repanier.be/fr/
- access to https://demo.repanier.be/fr/ on demand

Active customers groups :

https://apero.repanier.be/fr/
https://bloum.be/fr/
https://commande.coopeco-supermarche.be/fr/
https://commandes.gac-hamois.be/fr/
https://exceptionnel.repanier.be/fr/
https://gac-sombreffe.repanier.be/
https://gacmonssud.repanier.be/fr/
https://lepanierlensois.repanier.be/fr/
https://niveze.repanier.be/fr/
https://panier.gacavin.be/fr/
https://pigal.repanier.be/
https://ptidej.repanier.be/fr/

Active producers :

https://commande.lebuisson.be/fr/
https://saisonsvanbiervliet.be/fr/

Licence : GPL v3

Comment contribuer à Repanier?
------------------------------

  * En participant aux discussions entre utilisateurs et avec les développeur, lors des permanences, par téléphone ou par email, …
  * [En utilisant les tickets](https://github.com/pcolmant/repanier/issues)
  * [En envoyant un patch ou une demande de merge](https://guides.github.com/introduction/flow/)

Comment tester Repanier?
------------------------

Afin de pouvoir travailler en local sur Repanier, nous allons télécharger l'application et ses dépendances:

1. Clone du projet:

   git clone https://github.com/pcolmant/repanier.git

2. Initialisation et activation de l'environnement de développement, installation des dépendances:

   virtualenv -p python3 venv
   . venv/bin/activate
   pip install -r requirements/requirement.txt

3. Construction de la base de données et ajout des données factices:

   ./manage.py migrate
   ./manage.py loaddata fixtures/initial_users.yaml

4. Démarrage de l'application:

   ./manage.py runserver

Vous pouvez désormais accéder à l'application avec votre navigateur à l'adresse http://localhost:8000/ Pour s'authentifier comme administrateur vous pouvez utiliser: *admin* *secret*.
