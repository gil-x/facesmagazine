import csv
import datetime
import logging

import stripe
from django.shortcuts import get_object_or_404, render, redirect
from .models import Setting, Page, Issue, Subscription, Customer, Order
from .forms import ContactForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.views import View
from honeypot.decorators import check_honeypot

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

def get_customer_profile(user):
    if user.is_anonymous:
        return None
    customer_profiles = user.customer_set
    if customer_profiles.count() == 1:
        return customer_profiles.first()
    else:
        return None


def index(request, *args, **kwargs):
    context = {}
    context["homepage"] = True
    context["users"] = Setting.objects.first().users
    context["shop"] = Setting.objects.first().shop
    context["last_issue"] = Issue.objects.order_by('number').last()
    context["pages"] = Page.objects.all()
    # If request coming from 'prix-faces' URL:
    if kwargs["price"]:
        context["price"] = True
    return render(request, 'magazine/index.html', context)


def archives(request):
    context = {}
    context["pages"] = Page.objects.all()
    context["users"] = Setting.objects.first().users
    context["shop"] = Setting.objects.first().shop
    context["last_issue"] = Issue.objects.order_by('number').last()
    context["issues_availables"] = Issue.objects.filter(stock__gt=0)
    context["issues_empty"] = Issue.objects.filter(stock=0)
    context["customer"] = get_customer_profile(request.user)
    return render(request, 'magazine/archives.html', context)


def issue(request, number):
    context = {}
    context["pages"] = Page.objects.all()
    context["users"] = Setting.objects.first().users
    context["shop"] = Setting.objects.first().shop
    context["issue"] = Issue.objects.get(number=number)
    context["customer"] = get_customer_profile(request.user)
    return render(request, 'magazine/issue.html', context)


def contact(request):
    context = {}
    context["users"] = Setting.objects.first().users
    if request.method == 'POST':
        context["form"] = ContactForm(request.POST)
        if context["form"].is_valid(): 
            subject = context["form"].cleaned_data['subject']
            email = context["form"].cleaned_data['email']
            copy = context["form"].cleaned_data['copy']
            message = f"""
Message de {email},
envoyé le {datetime.datetime.now()},
via le formulaire du site de FACES Magazine
--
            
{context["form"].cleaned_data['message']}""" 
            recipients = list(settings.CONTACT_RECIPIENTS)
            if copy:
                recipients.append(email)
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)
            return render(request, 'magazine/thanks.html')
    else:
        context["form"] = ContactForm()
    return render(request, 'magazine/contact.html', context)


class Legal(ListView):
    model= Page
    context_object_name = 'pages'
    template_name= 'magazine/legal.html'


@login_required
def shop(request):
    context = {}
    context["pages"] = Page.objects.all()
    context["next_issue"] = Setting.objects.first().next_issue

    customer_profile = get_customer_profile(request.user)
    if not customer_profile:
        # TODO send to another page
        return redirect('index')

    if customer_profile.subscriber:
        return redirect('profile')

    if customer_profile.address and customer_profile.postal_code and customer_profile.city:
        context["profile_is_complete"] = True
    else:
        context["profile_is_complete"] = False

    context["subscription"] = Subscription.objects.filter(region=customer_profile.delivery_region).first()
    context["subscriptions"] = Subscription.objects.filter(region=customer_profile.delivery_region)

    return render(request, 'magazine/shop.html', context)


class CreateCheckoutSessionView(LoginRequiredMixin, View):
    """Ouvre une session Stripe Checkout et renvoie l'URL de paiement.

    Le client est ensuite redirigé vers cette URL par le navigateur ; c'est
    la méthode recommandée par Stripe depuis l'abandon de redirectToCheckout.
    """

    def post(self, request, *args, **kwargs):
        subscription = get_object_or_404(Subscription, pk=self.kwargs["pk"])

        customer_profile = get_customer_profile(request.user)
        if not customer_profile:
            return JsonResponse(
                {'error': "Aucun profil client n'est associé à ce compte."}, status=400
            )

        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            line_items=[
                {
                    'price_data': {
                        # Stripe attend un code ISO en minuscules.
                        'currency': subscription.currency.lower(),
                        'unit_amount': int(round(subscription.price * 100)),
                        'product_data': {
                            'name': f"FACES Magazine — abonnement {subscription.name}",
                        },
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                "user_id": request.user.id,
                "subscription_id": subscription.id,
            },
            mode='payment',
            success_url=f"{settings.DOMAIN}accounts/profile/",
            cancel_url=f"{settings.DOMAIN}shop/",
        )

        return JsonResponse({'url': checkout_session.url})


def _issues_covered_by(first_issue):
    """Libellé des quatre numéros couverts par un abonnement."""
    return "N° " + "-".join(str(first_issue + offset) for offset in range(4))


def fulfill_checkout_session(session):
    """Enregistre l'abonnement correspondant à une session Checkout payée.

    Appelée depuis le webhook, donc potentiellement plusieurs fois pour le
    même paiement : Stripe rejoue ses événements en cas de timeout.
    """
    session_id = session.get("id")

    if Order.objects.filter(stripe_session_id=session_id).exists():
        logger.info("Session Stripe %s déjà traitée, rien à faire.", session_id)
        return

    metadata = session.get("metadata") or {}
    try:
        user = User.objects.get(id=metadata["user_id"])
        subscription = Subscription.objects.get(id=metadata["subscription_id"])
    except (KeyError, ValueError, User.DoesNotExist, Subscription.DoesNotExist):
        logger.error(
            "Session Stripe %s inexploitable, métadonnées : %r", session_id, metadata
        )
        return

    customer_profile = get_customer_profile(user)
    if not customer_profile:
        logger.error(
            "Session Stripe %s : aucun profil client pour l'utilisateur %s.",
            session_id, user.pk,
        )
        return

    first_issue = Setting.objects.first().next_issue

    customer_profile.subscriber = True
    customer_profile.approval = True
    customer_profile.subscription = subscription
    customer_profile.first_issue = first_issue
    customer_profile.subscription_date = datetime.date.today()
    customer_profile.save()

    order = Order.objects.create(
        customer=customer_profile,
        item='SUBSC',
        subscription=subscription,
        date=datetime.date.today(),
        amount=subscription.price,
        currency=subscription.currency,
        order_info=_issues_covered_by(first_issue),
        stripe_session_id=session_id,
    )

    subject = "Votre abonnement à Faces Magazine"
    message = f"""
Vous êtes à présent abonné à la revue Faces, vous recevrez les 4 prochains numéros.
Prochain numéro : {first_issue}.

Votre facture est disponible à l'adresse {settings.DOMAIN}facture/{order.date}/
"""
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


@csrf_exempt
@require_POST
def stripe_webhook(request, *args, **kwargs):
    signature = request.headers.get('Stripe-Signature')
    if not signature:
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            request.body, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Charge utile illisible
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        # Signature absente ou falsifiée : la requête ne vient pas de Stripe
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        fulfill_checkout_session(event['data']['object'])

    # Toute erreur de traitement est journalisée sans renvoyer d'échec :
    # un rejeu par Stripe ne la corrigerait pas.
    return HttpResponse(status=200)


@login_required
def invoice(request, date):
    context = {}
    customer = Customer.objects.filter(user= request.user).first()

    context["invoice"] = Order.objects.filter(
        customer=customer,
        date=date).first()

    return render(request, 'magazine/invoice.html', context)


@staff_member_required
def invoices(request):
    context = {}
    context["invoices"] = Order.objects.all()
    return render(request, 'magazine/invoices-all.html', context)


@staff_member_required
def subscribers(request):
    context = {}
    context["customers"] = Customer.objects.filter(subscriber= True)
    for customer in context["customers"]:
        if Issue.objects.last().number > customer.first_issue + 3:
            customer.subscriber = False
            customer.first_issue = None
            customer.issues_to_go=0
            customer.save()
            pass
    return render(request, 'magazine/subscribers.html', context)


@staff_member_required
def issue_subscribers(request, number):
    context = {}
    context["number"] = number
    context["customers"] = Customer.objects.filter(
        Q(subscriber= True, first_issue=number - 3) |
        Q(subscriber= True, first_issue=number - 2) |
        Q(subscriber= True, first_issue=number - 1) |
        Q(subscriber= True, first_issue=number) 
    )
    return render(request, 'magazine/subscribers_issue.html', context)


@staff_member_required
def issue_subscribers_export(request, number, region):
    context = {}
    subscribers = Customer.objects.filter(
        Q(subscriber=True, region=region.upper(), first_issue=number - 3) |
        Q(subscriber=True, region=region.upper(), first_issue=number - 2) |
        Q(subscriber=True, region=region.upper(), first_issue=number - 1) |
        Q(subscriber=True, region=region.upper(), first_issue=number)
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="liste-envoi-faces{number}-{region}.csv"'
    writer = csv.writer(response)
    header = ['NOM', 'PRENOM', 'RAISON SOCIALE', 'ADRESSE', 'CP VILLE', 'COMPLÉMENT D\'ADRESSE', 'PAYS']
    if region == "suisse":
            header.insert(4, 'CASE POSTALE')
    writer.writerow(header)
    for subscriber in subscribers:
        fields = [
                subscriber.delivery_name,
                subscriber.delivery_firstname,
                subscriber.delivery_company,
                subscriber.delivery_address,
                f"{subscriber.delivery_postal_code} {subscriber.delivery_city}",
                subscriber.delivery_land,
            ]
        if region == "suisse":
            fields.insert(4, subscriber.delivery_postal_square)
        writer.writerow(fields)
    return response


@check_honeypot(field_name='name')
def contact_captcha(request):
    context = {}
    context["users"] = Setting.objects.first().users
    context["pages"] = Page.objects.all()

    if request.method == 'POST':
        context["form"] = ContactForm(request.POST)
        # Form is valid
        if context["form"].is_valid(): 
            subject = context["form"].cleaned_data['subject']
            email = context["form"].cleaned_data['email']
            copy = context["form"].cleaned_data['copy']
            message = f"""
Message de {email},
envoyé le {datetime.datetime.now()},
via le formulaire du site de FACES Magazine
--
            
{context["form"].cleaned_data['message']}""" 
            recipients = list(settings.CONTACT_RECIPIENTS)
            if copy:
                recipients.append(email)
            # Un envoi par destinataire : personne ne découvre les adresses des autres.
            for recipient in recipients:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient])
            return render(request, 'magazine/thanks.html')
        # Form not not valid
        else:
            # context["form"] = ContactForm()
            context["error"] = "True"
            # context["subject"] = context["form"].cleaned_data['subject'] or None
            return render(request, 'magazine/contact.html', context)
    else:
        context["form"] = ContactForm()
        return render(request, 'magazine/contact.html', context)
