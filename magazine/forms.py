from django import forms

from facesmagazine.antibot import HumanCheckMixin

from .models import Customer


class CustomerForm(forms.ModelForm):
    initial = {"subscriber": True}
    class Meta:
        model = Customer
        exclude = ['user', 'subscriber', 'first_issue', 'subscription_date',]


class ContactForm(HumanCheckMixin, forms.Form):
    """Formulaire ouvert aux visiteurs non inscrits, donc le plus exposé.

    Il était protégé par un captcha, remplacé par les contrôles invisibles de
    HumanCheckMixin : le lectorat de la revue est âgé et un captcha écartait
    autant de lecteurs que de robots.
    """

    subject = forms.CharField(max_length=100, label="Sujet")
    message = forms.CharField(widget=forms.Textarea, label="Message")
    email = forms.EmailField(label="Votre adresse e-mail")
    copy = forms.BooleanField(label="Recevoir une copie", required=False)
