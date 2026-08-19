#!/bin/bash
#
# Met le site à jour après un git pull.
# Ne redémarre pas l'application : cela se fait depuis l'administration
# Alwaysdata, Web > Sites > Redémarrer.
#
# Usage : ./scripts/deploy.sh
set -euo pipefail

PROJET="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJET/.venv/bin/python"
PIP="$PROJET/.venv/bin/pip"

cd "$PROJET"

if [ ! -x "$PYTHON" ]; then
    echo "Environnement virtuel introuvable dans $PROJET/.venv" >&2
    exit 1
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
