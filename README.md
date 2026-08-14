# FACES Magazine

Site de la revue d'architecture *FACES* : présentation des numéros, boutique
d'abonnement (paiement Stripe) et gestion des listes d'envoi pour l'association.

Django 5.2 LTS, Python 3.13, base SQLite.

## Installation

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env      # puis compléter les valeurs
```

Générer une clé secrète pour le `.env` :

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Restaurer les données (non versionnées) : placer `db.sqlite3` à la racine et le
contenu des médias dans `media/`, puis :

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

## Configuration

Toute la configuration variable est lue dans l'environnement, ou dans un fichier
`.env` à la racine. La liste complète des variables et leur rôle sont
documentés dans [.env.example](.env.example).

Il n'y a **pas** de fichier de réglages par environnement : le même
`facesmagazine/settings.py` sert en développement et en production, et c'est
`DJANGO_DEBUG` qui bascule les protections liées à HTTPS (HSTS, cookies
sécurisés, redirection SSL).

## Feuilles de style

Le CSS est compilé depuis SCSS. Après toute modification dans
`facesmagazine/static/scss/` :

```bash
cd facesmagazine/static/scss && ../../../.venv/bin/python compile.py
```

Cela régénère `static/css/main.css` et `main.min.css`, qui sont versionnés.

## Structure

- `magazine/` — numéros, pages éditoriales, boutique, commandes, exports
- `users/` — inscription avec activation par e-mail, connexion, profil client
- `templates/` — gabarit de base et pages d'erreur
- `facesmagazine/static/` — sources SCSS, CSS compilé, polices, images, JS

L'administration est servie sous `/backdoor/` et non `/admin/`.
