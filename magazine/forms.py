from django import forms
from .models import Customer
from captcha.fields import CaptchaField

class CustomerForm(forms.ModelForm):
    initial = {"subscriber": True}
    class Meta:
        model = Customer
        exclude = ['user', 'subscriber', 'first_issue', 'subscription_date',]


class ContactForm(forms.Form):
    subject = forms.CharField(max_length=100, label="Sujet")
    message = forms.CharField(widget=forms.Textarea)
    email = forms.EmailField(label="Votre adresse e-mail")
    copy = forms.BooleanField(label="Recevoir une copie", required=False)
    captcha = CaptchaField()
