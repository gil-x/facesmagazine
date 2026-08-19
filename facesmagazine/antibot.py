"""
Contrôles anti-robots invisibles pour l'utilisateur.

Le lectorat de la revue est âgé et peu à l'aise avec l'informatique : un
captcha écarterait autant de lecteurs que de robots. Les contrôles réunis ici
ne demandent rien à personne et n'ajoutent aucune étape au formulaire.

Aucun n'est infaillible isolément — un robot pilotant un vrai navigateur les
franchit tous. C'est leur superposition qui rend l'inscription automatisée
assez coûteuse pour ne plus valoir la peine, face à un site qui reçoit une
cinquantaine d'inscriptions légitimes par an.
"""
import time

from django import forms
from django.core import signing

SEL = "facesmagazine.antibot"

# Personne ne remplit un formulaire d'inscription en moins de trois secondes.
# Un robot, lui, le soumet dans la foulée du chargement de la page.
DELAI_MINIMUM = 3

# Au-delà, le jeton est périmé : cela empêche de récolter un formulaire une
# fois puis de rejouer indéfiniment le même jeton.
DELAI_MAXIMUM = 4 * 60 * 60

MESSAGE_ECHEC = (
    "Votre inscription n'a pas pu être validée. Merci de recharger la page "
    "et de remplir à nouveau le formulaire."
)


def reponse_attendue(jeton):
    """Transformation que le JavaScript de la page reproduit à l'identique.

    Volontairement triviale : elle ne prouve pas une intention humaine, mais
    qu'un moteur JavaScript a exécuté la page, ce que ne fait pas un client
    HTTP qui poste directement le formulaire.
    """
    return jeton[::-1]


class HumanCheckMixin:
    """Ajoute deux champs cachés à un formulaire, et les vérifie.

    À placer avant la classe de formulaire dans la liste des bases :

        class SignupForm(HumanCheckMixin, UserCreationForm):
            ...

    Les champs sont déclarés dans __init__ plutôt qu'au niveau de la classe
    pour rester compatible avec les ModelForm, dont la métaclasse ne collecte
    pas les champs des bases qui ne sont pas elles-mêmes des formulaires.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ouverture'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput,
            initial=signing.dumps(time.time(), salt=SEL),
        )
        self.fields['presence'] = forms.CharField(
            required=False,
            widget=forms.HiddenInput,
        )

    def clean(self):
        donnees = super().clean()

        jeton = self.data.get('ouverture', '')
        try:
            ouvert_a = signing.loads(jeton, salt=SEL, max_age=DELAI_MAXIMUM)
        except signing.BadSignature:
            # Jeton absent, falsifié ou périmé.
            raise forms.ValidationError(MESSAGE_ECHEC)

        if time.time() - ouvert_a < DELAI_MINIMUM:
            raise forms.ValidationError(MESSAGE_ECHEC)

        if self.data.get('presence', '') != reponse_attendue(jeton):
            raise forms.ValidationError(MESSAGE_ECHEC)

        return donnees
