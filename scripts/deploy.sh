#!/bin/bash
#
# Met le site à jour après un git pull.
# Ne redémarre pas l'application : cela se fait depuis l'administration
# Alwaysdata, Web > Sites > Redémarrer.
#
# Usage : ./scripts/deploy.sh [--nouvelle-base]
#
# --nouvelle-base autorise le déploiement sans base existante. À n'employer
# que pour une installation réellement vierge : sans cette option, le script
# refuse de créer une base vide par mégarde.
set -euo pipefail

NOUVELLE_BASE=0
[ "${1:-}" = "--nouvelle-base" ] && NOUVELLE_BASE=1

PROJET="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJET/.venv/bin/python"
PIP="$PROJET/.venv/bin/pip"

cd "$PROJET"

if [ ! -x "$PYTHON" ]; then
    echo "Environnement virtuel introuvable dans $PROJET/.venv" >&2
    echo "Le créer avec : python3.13 -m venv .venv" >&2
    exit 1
fi

# La configuration est vérifiée avant toute modification : inutile d'installer
# des dépendances ou d'effacer les fichiers statiques pour échouer ensuite.
if [ ! -f "$PROJET/.env" ]; then
    cat >&2 <<'FIN'
Fichier .env introuvable à la racine du projet.

La configuration ne peut pas venir du seul champ « Variables d'environnement »
de l'administration Alwaysdata : celui-ci alimente le processus qui sert le
site, mais pas les commandes lancées en SSH comme celle-ci.

Voir l'étape 5 de DEPLOY.md.
FIN
    exit 1
fi

# manage.py est passé par ici plutôt que python -c : lui seul définit
# DJANGO_SETTINGS_MODULE, sans quoi l'erreur remontée serait trompeuse.
if ! "$PYTHON" manage.py check >/dev/null 2>&1; then
    echo "La configuration est incomplète. Détail :" >&2
    echo >&2
    "$PYTHON" manage.py check 2>&1 | grep -E "^[a-zA-Z_.]+(Error|Exception|Configured):" | tail -2 >&2
    echo >&2
    echo "Compléter $PROJET/.env — voir l'étape 5 de DEPLOY.md." >&2
    exit 1
fi

# Chemins tels que Django les résout réellement, plutôt que recopiés à la main.
lire_reglage() {
    DJANGO_SETTINGS_MODULE=facesmagazine.settings "$PYTHON" -c "
import django; django.setup()
from django.conf import settings
print($1)"
}

BASE="$(lire_reglage "settings.DATABASES['default']['NAME']")"
MEDIAS="$(lire_reglage "settings.MEDIA_ROOT")"
DOSSIER_BASE="$(dirname "$BASE")"

# Le guide a longtemps utilisé « COMPTE » comme espace réservé. En oublier un
# donne une erreur déroutante : le dossier semble exister alors que le chemin
# configuré désigne un autre endroit.
if grep -q 'COMPTE' "$PROJET/.env"; then
    echo "Le fichier .env contient encore l'espace réservé « COMPTE » :" >&2
    grep -n 'COMPTE' "$PROJET/.env" | sed 's/^/  /' >&2
    echo >&2
    echo "Le remplacer par le nom du compte :  sed -i \"s/COMPTE/\$USER/g\" .env" >&2
    exit 1
fi

if [ ! -d "$DOSSIER_BASE" ]; then
    echo "Le dossier de la base n'existe pas : $DOSSIER_BASE" >&2
    echo "Le créer avec : mkdir -p $DOSSIER_BASE" >&2
    exit 1
fi

# SQLite crée des fichiers -wal et -shm à côté de la base : le droit d'écriture
# sur le dossier est nécessaire, pas seulement sur le fichier.
if [ ! -w "$DOSSIER_BASE" ]; then
    echo "Le dossier de la base n'est pas accessible en écriture : $DOSSIER_BASE" >&2
    echo "SQLite doit pouvoir y créer ses fichiers -wal et -shm." >&2
    exit 1
fi

if [ ! -s "$BASE" ] && [ "$NOUVELLE_BASE" -eq 0 ]; then
    cat >&2 <<FIN
Base de données absente ou vide : $BASE

Poursuivre créerait une base neuve et le site remonterait sans aucun numéro,
abonné ni commande. Transférer d'abord la base de production :

    scp db.sqlite3 $USER@ssh-$USER.alwaysdata.net:$BASE

S'il s'agit réellement d'une installation vierge, relancer avec :

    ./scripts/deploy.sh --nouvelle-base
FIN
    exit 1
fi

if [ ! -d "$MEDIAS" ] || [ -z "$(ls -A "$MEDIAS" 2>/dev/null)" ]; then
    echo "Attention : $MEDIAS est absent ou vide, les couvertures ne s'afficheront pas." >&2
fi

echo "→ Dépendances"
"$PIP" install --quiet --upgrade -r requirements.txt

echo "→ Sauvegarde de la base avant migration"
"$PROJET/scripts/backup.sh" --silencieux

echo "→ Migrations"
"$PYTHON" manage.py migrate --noinput

echo "→ Fichiers statiques"
"$PYTHON" manage.py collectstatic --noinput --clear

echo "→ Contrôle de la configuration de production"
"$PYTHON" manage.py check --deploy --fail-level WARNING

echo
echo "Terminé. Redémarrer le site depuis l'administration Alwaysdata."
