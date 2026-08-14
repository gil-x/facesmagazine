from django.urls import path, include
from . import views


urlpatterns = [
    path('', include('django.contrib.auth.urls')),
    path('login/', views.LoginWithPages.as_view()),
    path('inscription/', views.registration, name='registration'),
    # Le motif d'origine bornait le jeton à 20 caractères, ce qui correspondait
    # au condensat SHA-1 de Django 2.2. Depuis Django 3.1 il fait 32 caractères
    # et l'URL ne se construisait plus. Django lui-même n'impose plus aucune
    # contrainte de longueur ici : on fait pareil.
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit', views.edit_profile, name='edit_profile'),
]