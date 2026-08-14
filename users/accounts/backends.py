from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """Connexion par nom d'utilisateur ou par adresse e-mail, sans distinction
    de casse.

    Hérite de ModelBackend pour conserver ses garde-fous, en particulier le
    refus des comptes désactivés : la version précédente n'en héritait pas et
    ne vérifiait pas is_active.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        champ = 'email' if '@' in username else UserModel.USERNAME_FIELD
        candidats = list(
            UserModel._default_manager.filter(**{f'{champ}__iexact': username})
        )

        if not candidats:
            # Occuper le même temps qu'une vérification réelle : sans cela, la
            # rapidité de la réponse trahirait l'absence de compte.
            UserModel().set_password(password)
            return None

        # Django n'impose pas l'unicité des adresses e-mail, et une douzaine
        # de lecteurs partagent la leur avec un second compte. Un get() lèverait
        # MultipleObjectsReturned et renverrait une erreur 500 à ces personnes.
        for utilisateur in candidats:
            if (utilisateur.check_password(password)
                    and self.user_can_authenticate(utilisateur)):
                return utilisateur
        return None
