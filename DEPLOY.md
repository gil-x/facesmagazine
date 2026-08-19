# Déploiement sur Alwaysdata

Le site tourne en Python 3.13 / Django 5.2 LTS, servi par uWSGI, avec une base
SQLite. Remplacer `COMPTE` par le nom du compte Alwaysdata dans tout ce qui suit.

## Principe

Le code est dans un dossier, **les données sont ailleurs**. La base et les
médias vivent hors de l'arborescence du code, pour qu'un redéploiement, un
`git checkout` malheureux ou une suppression du dossier ne puissent pas les
emporter.

```
/home/COMPTE/
├── www/facesmagazine/     ← le dépôt git, remplaçable à volonté
│   ├── .venv/
│   └── staticfiles/       ← généré par collectstatic
└── data/                  ← jamais touché par un déploiement
    ├── db.sqlite3
    ├── media/
    └── sauvegardes/
```

## 1. Préparer les dossiers

```bash
ssh COMPTE@ssh-COMPTE.alwaysdata.net
mkdir -p ~/data/media ~/data/sauvegardes
```

Étape à ne pas sauter : sans ces dossiers, le déploiement s'arrête sur
`unable to open database file`. SQLite a besoin d'écrire non seulement la
base, mais aussi ses fichiers `-wal` et `-shm` dans le même dossier.

## 2. Déposer le code

```bash
cd ~/www
git clone <url-du-depot> facesmagazine
cd facesmagazine
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`requirements-dev.txt` n'est utile que pour recompiler les feuilles de style ;
inutile sur le serveur, le CSS compilé est versionné.

## 3. Transférer les données

Depuis le poste local :

```bash
scp db.sqlite3 COMPTE@ssh-COMPTE.alwaysdata.net:~/data/db.sqlite3
rsync -avz media/ COMPTE@ssh-COMPTE.alwaysdata.net:~/data/media/
```

## 4. Créer le site dans l'administration

**Web → Sites → Ajouter un site**, type **Python WSGI** :

| Champ | Valeur |
|---|---|
| Chemin de l'application | `/home/COMPTE/www/facesmagazine/facesmagazine/wsgi.py` |
| Répertoire de travail | `/home/COMPTE/www/facesmagazine` |
| Répertoire virtualenv | `/home/COMPTE/www/facesmagazine/.venv` |
| Version de Python | 3.13 |

Le répertoire de travail doit bien être la racine du projet, sinon
`facesmagazine.settings` reste introuvable.

## 5. Déclarer la configuration

Deux choses ont besoin de cette configuration : **le site servi par uWSGI**, et
**les commandes lancées en SSH** (migrations, fichiers statiques, sauvegardes).

Le champ « Variables d'environnement » de l'administration n'alimente que le
premier : il est transmis au processus du site, pas à une session SSH. Y
déclarer la configuration fait donc échouer `deploy.sh` avec
`Set the DJANGO_SECRET_KEY environment variable`.

On utilise donc un **fichier `.env` à la racine du projet**, que Django lit
dans les deux cas. Une seule source, aucune dérive possible.

**Laisser vide le champ « Variables d'environnement » de l'administration.**
S'il est rempli, il a priorité sur le fichier pour le site mais pas pour les
commandes : les deux finiraient par diverger sans prévenir. (Pour mémoire, son
format est `FOO=bar LOREM=ipsum`, séparé par des espaces sur une seule ligne.)

### Créer le fichier

Le bloc ci-dessous refuse d'écraser un fichier existant. C'est délibéré :
on reprend souvent une procédure interrompue, et réexécuter un `cat > .env`
ferait perdre les valeurs déjà saisies, clé secrète comprise.

```bash
cd ~/www/facesmagazine
[ -e .env ] && { echo "Un .env existe déjà : le compléter à la main."; } || cat > .env <<FIN
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=facesmagazine.ch,www.facesmagazine.ch
DJANGO_CSRF_TRUSTED_ORIGINS=https://facesmagazine.ch,https://www.facesmagazine.ch
DJANGO_DOMAIN=https://www.facesmagazine.ch/

DJANGO_DB_PATH=$HOME/data/db.sqlite3
DJANGO_MEDIA_ROOT=$HOME/data/media

DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp-$USER.alwaysdata.net
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=info@facesmagazine.ch
CONTACT_RECIPIENTS=info@facesmagazine.ch

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
FIN
chmod 600 .env
```

Les chemins et le serveur SMTP sont résolus à la création : `$HOME` et
`$USER` sont ceux du compte, il n'y a rien à remplacer à la main. Vérifier tout
de même le nom du serveur SMTP dans l'administration, section e-mails.

Il reste à compléter les valeurs laissées vides. Générer la clé secrète :

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Changer `DJANGO_SECRET_KEY` déconnecte tout le monde et invalide les liens de
réinitialisation de mot de passe en cours. Sans conséquence ici : la clé
d'origine n'est de toute façon plus disponible.

`STRIPE_WEBHOOK_SECRET` reste vide jusqu'à l'étape 8, qui exige que le domaine
soit en place.

### Deux précautions

Le fichier n'est pas versionné et vit dans le dossier du code : **un
`git clone` neuf ne le ramènera pas**. Garder les valeurs dans un gestionnaire
de mots de passe, accessible à au moins deux personnes de l'association.

`chmod 600` n'est pas décoratif : sans lui, le fichier est lisible par les
autres comptes de la machine.

À quoi sert chaque variable :

| Variable | Valeur |
|---|---|
| `DJANGO_SECRET_KEY` | une clé neuve, voir ci-dessus |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | les domaines servis, séparés par des virgules |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | les mêmes, **avec le schéma `https://`** |
| `DJANGO_DOMAIN` | URL publique **avec le slash final**, utilisée par Stripe |
| `DJANGO_DB_PATH` | la base, hors du dossier du code |
| `DJANGO_MEDIA_ROOT` | les couvertures, hors du dossier du code |
| `DJANGO_EMAIL_BACKEND` | le backend SMTP, sinon les mails partent dans le vide |
| `EMAIL_*` | le compte d'envoi Alwaysdata |
| `DEFAULT_FROM_EMAIL` | expéditeur des messages du site |
| `CONTACT_RECIPIENTS` | destinataires du formulaire de contact, virgules |
| `STRIPE_SECRET_KEY` | `sk_test_…` tant qu'on valide, `sk_live_…` ensuite |
| `STRIPE_WEBHOOK_SECRET` | `whsec_…`, obtenu à l'étape 8 |

### Vérifier avant d'aller plus loin

```bash
.venv/bin/python manage.py check --deploy
```

Ne doit rien signaler. En cas d'erreur `Set the … environment variable`, le
fichier `.env` n'est pas là où Django le cherche : il doit être à la racine du
projet, à côté de `manage.py`.

## 6. Première mise en service

```bash
cd ~/www/facesmagazine
./scripts/deploy.sh
```

Le script installe les dépendances, applique les migrations, rassemble les
fichiers statiques et vérifie la configuration de production. Redémarrer
ensuite le site depuis l'administration (**Web → Sites → Redémarrer**).

## 7. Vérifications

```bash
.venv/bin/python manage.py check --deploy   # ne doit rien signaler
```

Puis, dans un navigateur : la page d'accueil, un numéro avec sa couverture
(vérifie que `DJANGO_MEDIA_ROOT` est bon), le formulaire de contact, la
connexion, et `/backdoor/` pour l'administration.

Les couvertures sont servies par `StaticAndMediaMiddleware`, pas par une
configuration de l'hébergeur : il n'y a rien à déclarer côté Alwaysdata pour
`/media/`, et le comportement est le même en développement et en production.

Les journaux d'erreur sont dans `/home/COMPTE/admin/logs/uwsgi/`. Le site y
écrit à chaque démarrage la configuration qu'il utilise **réellement** :

```
Site démarré — DEBUG=False, base=/home/COMPTE/data/db.sqlite3, médias=…, hôtes=[…]
```

C'est la première chose à regarder devant une erreur inexpliquée. Si ces
chemins ne sont pas ceux du `.env`, c'est que le champ « Variables
d'environnement » de l'administration n'est pas vide : il a priorité sur le
fichier pour le site, mais reste invisible aux commandes SSH. Une base
parfaitement accessible en ligne de commande donne alors un
`unable to open database file` côté site.

## 8. Webhook Stripe

Le secret du webhook dépend de l'URL : il ne peut être créé qu'une fois le
domaine en place.

Dans le tableau de bord Stripe, créer un endpoint sur
`https://www.facesmagazine.ch/webhooks/stripe/`, abonné au seul événement
`checkout.session.completed`. Reporter le `whsec_…` obtenu dans
`STRIPE_WEBHOOK_SECRET`, puis redémarrer le site.

Sans ce secret, tout paiement aboutit chez Stripe **sans que l'abonnement soit
enregistré** sur le site. C'est le point le plus facile à oublier.

## 9. Tâches planifiées

Dans **Avancé → Tâches planifiées** :

| Fréquence | Commande |
|---|---|
| chaque nuit | `/home/COMPTE/www/facesmagazine/scripts/backup.sh` |
| chaque semaine | `/home/COMPTE/www/facesmagazine/.venv/bin/python /home/COMPTE/www/facesmagazine/manage.py clearsessions` |

Sans `clearsessions`, la table des sessions gonfle indéfiniment — elle avait
atteint 6 211 lignes sur l'ancienne installation.

## Mises à jour ultérieures

```bash
cd ~/www/facesmagazine && git pull && ./scripts/deploy.sh
```

puis redémarrer le site depuis l'administration.

## Surveillance

Le site est tombé parce que personne n'a vu passer l'impayé. À mettre en place
en même temps que la mise en ligne :

- une surveillance externe de la page d'accueil, avec alerte par e-mail
  (UptimeRobot ou équivalent, l'offre gratuite suffit) ;
- le paiement automatique de l'hébergement, et une adresse de facturation
  relevée par **au moins deux personnes** de l'association ;
- une copie des sauvegardes hors d'Alwaysdata : le script les écrit sur le même
  serveur, ce qui protège d'une erreur de manipulation mais pas d'une perte du
  compte.

## Points à surveiller après la mise en ligne

**SQLite et le multi-processus.** uWSGI peut lancer plusieurs processus, qui
écrivent alors dans le même fichier. La configuration limite le risque (mode
WAL, transactions immédiates, attente de 20 s), et le trafic du site est très
faible. Si des erreurs `database is locked` apparaissent dans les journaux, il
faut soit réduire le site à un seul processus, soit basculer sur PostgreSQL,
inclus dans l'offre Alwaysdata.

**Délivrabilité des e-mails.** Le site envoie des confirmations d'abonnement et
des liens d'activation. Vérifier que les enregistrements SPF, DKIM et DMARC du
domaine autorisent bien Alwaysdata à émettre pour `facesmagazine.ch`, sans quoi
ces messages finiront en indésirables.

**Limitation par adresse IP.** Non encore en place. Elle suppose de savoir quel
en-tête l'hébergeur transmet pour identifier le visiteur — à vérifier sur le
serveur avant de l'activer, faute de quoi elle bloquerait tout le monde ou
personne.
