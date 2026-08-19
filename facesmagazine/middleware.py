from django.conf import settings
from whitenoise.middleware import WhiteNoiseMiddleware


class StaticAndMediaMiddleware(WhiteNoiseMiddleware):
    """Sert les fichiers statiques et les fichiers déposés par l'administration.

    Django refuse par construction de servir MEDIA_ROOT hors mode debug :
    l'assistant urls.static() renvoie une liste vide dès que DEBUG vaut False.
    Le site se retrouvait donc en ligne sans aucune couverture de numéro, alors
    que tout s'affichait en développement.

    Confier les deux au même intergiciel supprime cet écart : ce qui est
    vérifié en local est ce qui tourne en production.

    Seul MEDIA_ROOT est exposé, pas son dossier parent — la base de données
    vit à côté et n'a rien à faire sur le Web.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        if settings.MEDIA_ROOT and settings.MEDIA_URL:
            self.add_files(str(settings.MEDIA_ROOT), prefix=settings.MEDIA_URL)
