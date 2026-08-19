#!/bin/bash
#
# Sauvegarde la base et les médias, et fait le ménage dans les anciennes copies.
# Prévu pour une tâche planifiée quotidienne.
#
# Usage : ./scripts/backup.sh [--silencieux]
#
# La base est copiée avec « sqlite3 .backup » et non avec cp : cette commande
# prend un verrou cohérent et produit un fichier exploitable même si le site
# écrit au même moment.
set -euo pipefail

PROJET="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE="${DJANGO_DB_PATH:-$PROJET/db.sqlite3}"
MEDIAS="${DJANGO_MEDIA_ROOT:-$PROJET/media}"
DESTINATION="${FACES_BACKUP_DIR:-$HOME/data/sauvegardes}"
RETENTION_JOURS=30

SILENCIEUX=0
[ "${1:-}" = "--silencieux" ] && SILENCIEUX=1
dire() { [ "$SILENCIEUX" -eq 1 ] || echo "$@"; }

horodatage="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DESTINATION"

# --- Base de données ---
cible="$DESTINATION/db-$horodatage.sqlite3"
sqlite3 "$BASE" ".backup '$cible'"

# Une sauvegarde qu'on n'a pas relue n'est pas une sauvegarde.
if [ "$(sqlite3 "$cible" 'pragma integrity_check;')" != "ok" ]; then
    echo "ÉCHEC : la sauvegarde $cible est corrompue" >&2
    exit 1
fi
gzip -f "$cible"
dire "Base sauvegardée : $cible.gz ($(du -h "$cible.gz" | cut -f1))"

# --- Médias ---
# Les couvertures ne changent qu'à la parution d'un numéro : une synchronisation
# incrémentale suffit, inutile de dupliquer 67 Mo chaque nuit.
if [ -d "$MEDIAS" ]; then
    rsync -a --delete "$MEDIAS/" "$DESTINATION/media/"
    dire "Médias synchronisés : $(du -sh "$DESTINATION/media" | cut -f1)"
fi

# --- Ménage ---
supprimes="$(find "$DESTINATION" -maxdepth 1 -name 'db-*.sqlite3.gz' -mtime "+$RETENTION_JOURS" -print -delete | wc -l)"
[ "$supprimes" -gt 0 ] && dire "Sauvegardes de plus de $RETENTION_JOURS jours supprimées : $supprimes"

dire "Sauvegardes conservées : $(find "$DESTINATION" -maxdepth 1 -name 'db-*.sqlite3.gz' | wc -l)"
