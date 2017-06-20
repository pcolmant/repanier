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

Development instructions
------------------------

 1. Clone repository:

    git clone https://github.com/pcolmant/repanier.git

 2. Initialize python virtual environment

    virtualenv -p python3 venv

 3. Activate it

    . venv/bin/activate

 4. Install python dependencies

    pip install -r requirements/requirement.txt

 5. Synchronize database

    ./manage.py migrate

 6. Launch the application

    ./manage.py runserver
