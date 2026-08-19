"""
Point d'entrée WSGI du site FACES Magazine.

https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import logging
import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facesmagazine.settings')

application = get_wsgi_application()

# Journalise la configuration effective au démarrage du site.
#
# Le processus qui sert le site et les commandes lancées en SSH ne lisent pas
# forcément les mêmes sources : les variables d'environnement injectées par
# l'hébergeur l'emportent sur le fichier .env, et l'écart ne se manifeste que
# par une erreur sans rapport apparent — « unable to open database file » pour
# un chemin pourtant correct en ligne de commande. Cette trace le rend visible
# dès le démarrage, dans le journal du serveur.
logging.getLogger(__name__).info(
    "Site démarré — DEBUG=%s, base=%s, médias=%s, hôtes=%s",
    settings.DEBUG,
    settings.DATABASES['default']['NAME'],
    settings.MEDIA_ROOT,
    settings.ALLOWED_HOSTS,
)
