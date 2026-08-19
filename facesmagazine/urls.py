from django.contrib import admin
from django.urls import path, include

from magazine import views as magazine_views

urlpatterns = [

    path('', include('magazine.urls')),

    # Account
    path('accounts/', include('users.urls')),

    # Contact
    path('contact/', magazine_views.contact_captcha, name='contact_captcha'),

    # Legal
    path('legal/', magazine_views.Legal.as_view(), name='legal'),

    # admin (l'URL est volontairement inhabituelle : /admin/ n'existe pas)
    path('backdoor/', admin.site.urls),

]

# Les fichiers de MEDIA_ROOT sont servis par StaticAndMediaMiddleware, en
# développement comme en production. L'assistant static() n'est pas employé :
# il ne produit aucune route hors mode debug, ce qui faisait disparaître les
# couvertures une fois le site en ligne.
