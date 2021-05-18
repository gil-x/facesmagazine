import datetime, csv
import stripe
from django.shortcuts import render, redirect
from .models import Setting, Page, Issue, Subscription, Customer, Order
from .forms import ContactForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, DetailView, ListView
from django.views import View
from honeypot.decorators import check_honeypot

stripe.api_key = settings.STRIPE_SECRET_KEY

def get_customer_profile(user):
    if user.is_anonymous:
        return None
    customer_profiles = user.customer_set
    if customer_profiles.count() == 1:
        return customer_profiles.first()
    else:
        return None


def index(request):
    context = {}
    context["homepage"] = True
    context["users"] = Setting.objects.first().users
    context["shop"] = Setting.objects.first().shop
    context["last_issue"] = Issue.objects.order_by('number').last()
    context["pages"] = Page.objects.all()
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
            recipients = ['info@facesmagazine.ch', 'contact@elizaculea.com']
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
        context['key'] = settings.STRIPE_PUBLISHABLE_KEY
    else:
        context["profile_is_complete"] = False

    context["subscription"] = Subscription.objects.filter(region=customer_profile.delivery_region).first()
    context["subscriptions"] = Subscription.objects.filter(region=customer_profile.delivery_region)

    return render(request, 'magazine/shop.html', context)


def subscription(request):
    context = {}
    customer_profiles = request.user.customer_set
    if customer_profiles.count() == 1:
        customer_profile = customer_profiles.first()
    else:
        # TODO send to another page
        pass

    subscriptions = Subscription.objects.filter(region=customer_profile.delivery_region)
    subscription = Subscription.objects.filter(region=customer_profile.delivery_region, name=request.POST.get('package')).first()

    print(f"*** subscription: {subscription}")

    if request.method == 'POST':
        paid = False
        # paid = True
        print(f"request.POST.get('package')= {request.POST.get('package')}")

        if request.POST.get('package') in [s.name for s in subscriptions]:
            print("Package OK")
            context["subscription"] = request.POST.get('package')
        else:
            print("Package not OK")
            print(f"[s.name for s in subscriptions] : {[s.name for s in subscriptions]}")

        try:
            # Create charge
            charge = stripe.Charge.create(
                amount=int(subscription.price * 100),
                currency=Subscription.objects.filter(region=customer_profile.delivery_region).first().currency.lower(),
                description=request.POST.get('package'),
                source=request.POST['stripeToken'],
                receipt_email=request.user.email,
            )

            paid = True
            # TODO test and rise custom error if value not possible
        except stripe.error.CardError as e:
            # The card has been declined
            pass

        if paid:
            customer_profile.subscriber = True
            customer_profile.subscription = subscription
            customer_profile.first_issue = Setting.objects.first().next_issue
            customer_profile.subscription_date = datetime.date.today()
            customer_profile.save()

            order = Order()
            order.customer = customer_profile
            order.item = 'SUBSC'
            order.subscription = subscription
            order.date = datetime.date.today()
            order.amount = subscription.price
            order.currency = subscription.currency
            order.order_info = f"N° {Setting.objects.first().next_issue}-{Setting.objects.first().next_issue + 1}-{Setting.objects.first().next_issue + 2}-{Setting.objects.first().next_issue + 3}"
            order.save()

            subject = "Votre abonnement à Faces Magazine"
            message = f"""
Vous êtes à présent abonné à la revue Faces, vous recevrez les 4 prochains numéros.
Prochain numéro : {Setting.objects.first().next_issue}.

Votre facture est disponible à l'adresse {request.scheme + "://" + get_current_site(request).domain}/facture/{order.date}
"""
            recipients = [request.user.email]
            recipients.append(request.user.email)
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)
        else:
            pass
        context["customer_profile"] = customer_profile
        return render(request, 'magazine/subscription.html', context)

    else:
        # Not a POST, redirect to homepage.
        return redirect('index')

from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.staticfiles.storage import staticfiles_storage

class CreateCheckoutSessionView(View):
    def post(self, request, *args, **kwargs):
        subscription_id = self.kwargs["pk"]
        subscription = Subscription.objects.get(id=subscription_id)

        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': subscription.currency,
                        'unit_amount': int(subscription.price * 100),
                        'product_data': {
                            'name': f"FACES Magazine, Abonnement\n{subscription.name}",
                            'images': ['https://www.facesmagazine.ch/media/issues/FACES_78_couv.jpg'],
                        },
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                "user_id": request.user.id,
                "subscription_id": subscription_id,
            },
            mode='payment',
            success_url=f"{settings.DOMAIN}accounts/profile/",
            cancel_url=f"{settings.DOMAIN}shop/",
        )

        return JsonResponse({
            'id': checkout_session.id
        })


@csrf_exempt
def stripe_webhook(request, *args, **kwargs):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    STRIPE_WEBHOOK_SECRET = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_email = session["customer_details"]["email"]
        user_id = session["metadata"]["user_id"]
        request_user = User.objects.get(id=user_id)
        subscription_id = session["metadata"]["subscription_id"]
        customer_profile = get_customer_profile(request_user)
        subscription =  Subscription.objects.get(id=subscription_id)

        customer_profile.subscriber = True
        customer_profile.approval = True
        customer_profile.subscription = subscription
        customer_profile.first_issue = Setting.objects.first().next_issue
        customer_profile.subscription_date = datetime.date.today()
        customer_profile.save()

        order = Order()
        order.customer = customer_profile
        order.item = 'SUBSC'
        order.subscription = subscription
        order.date = datetime.date.today()
        order.amount = subscription.price
        order.currency = subscription.currency
        order.order_info = f"N° {Setting.objects.first().next_issue}-{Setting.objects.first().next_issue + 1}-{Setting.objects.first().next_issue + 2}-{Setting.objects.first().next_issue + 3}"
        order.save()

        subject = "Votre abonnement à Faces Magazine"
        message = f"""
Vous êtes à présent abonné à la revue Faces, vous recevrez les 4 prochains numéros.
Prochain numéro : {Setting.objects.first().next_issue}.

Votre facture est disponible à l'adresse {request.scheme + "://" + get_current_site(request).domain}/facture/{order.date}
"""
        recipients = [request_user.email]
        recipients.append(request_user.email)
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)

    # Passed signature verification
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
    date = Order.objects.first().date
    print(f"date: {date}")
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
            recipients = ['info@facesmagazine.ch', 'contact@elizaculea.com', 'g.ladowitch@lautretribu.com']
            if copy:
                recipients.append(email)
            for mail in recipients:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [mail])
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
