from django.shortcuts import render, redirect

from django.contrib.auth.views import LoginView
from django.contrib.auth import login

from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from .tokens import account_activation_token

from django.contrib.auth.models import User

from magazine.models import Page, Customer
from .forms import SignupForm
from magazine.forms import CustomerForm

from django.contrib.sites.shortcuts import get_current_site


from django.contrib.auth.decorators import login_required


def get_customer_profile(user):
    customer_profiles = user.customer_set
    if customer_profiles.count() == 1:
        return customer_profiles.first()
    else:
        return None


def registration(request):
    context = {}
    context["pages"] = Page.objects.all()

    if request.method == 'POST':
        context["form"] = SignupForm(request.POST)

        if context["form"].is_valid():
            user = context["form"].save(commit=False)
            user.is_active = False
            user.save()
            current_site = get_current_site(request)
            mail_subject = 'Activez votre compte sur Faces'
            message = render_to_string('registration/acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)).encode().decode(),
                'token': account_activation_token.make_token(user),
            })
            to_email = context["form"].cleaned_data.get('email')
            email = EmailMessage(
                        mail_subject, message, to=[to_email]
            )
            email.send()
            return render(request, 'registration/confirmation.html')
    else:
        context["form"] = SignupForm()

    return render(request, 'registration/registration.html', context)


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        new_customer = Customer()
        new_customer.user = user
        new_customer.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return render(request, 'registration/activation_success.html', {})
    else:
        return render(request, 'registration/activation_fail.html', {})


class LoginWithPages(LoginView):
    pass
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     context["pages"] = Page.objects.all()
    #     return context

    # def get(self, request):
    #     context["pages"] = Page.objects.all()
    #     return render(request, 'registration/login.html', self.context)


@login_required
def profile(request):
    context = {}

    customer_profile = get_customer_profile(request.user)

    if customer_profile:
        context["customer_profile"] = customer_profile
        if customer_profile.address and customer_profile.postal_code and customer_profile.city:
            context["profile_is_complete"] = True
        else:
            context["profile_is_complete"] = False
    
    return render(request, 'magazine/profile.html', context)


@login_required
def edit_profile(request):
    context = {}
    context["pages"] = Page.objects.all()

    customer_profile = get_customer_profile(request.user)
    context["form"] = CustomerForm(instance=customer_profile)

    if request.method == 'POST':
        context["form"] = CustomerForm(request.POST, instance=customer_profile)
        if context["form"].is_valid():
            context["form"].save()
            return redirect('profile')
    return render(request, 'magazine/profile-edit.html', context)

