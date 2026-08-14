from django import forms


class TrixWidget(forms.Widget):
    """Éditeur visuel Trix pour les champs HTML de l'administration.

    Remplace CKEditor 4, en fin de vie et porteur de failles non corrigées.
    Les fichiers de Trix sont déposés dans les statiques du site : aucune
    dépendance Python, aucun appel à un CDN, rien à mettre à jour.

    Trix fonctionne par paire : un champ caché porte la valeur réellement
    soumise, l'élément <trix-editor> ne sert qu'à l'édition.
    """

    template_name = 'magazine/widgets/trix.html'

    class Media:
        css = {'all': ('trix/trix.css', 'trix/trix-admin.css')}
        js = ('trix/trix.umd.min.js',)
