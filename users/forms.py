from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from facesmagazine.antibot import HumanCheckMixin


class LoginForm(forms.Form):
    username = forms.CharField(label="Nom d'utilisateur ", max_length=30)
    password = forms.CharField(label="Mot de passe ", widget=forms.PasswordInput)


class SignupForm(HumanCheckMixin, UserCreationForm):
    email = forms.EmailField(max_length=200, help_text='Required')
    password2 = forms.CharField(label="Mot de passe (vérification)", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')