from django.urls import path, re_path, include
from . import views

# from django.views.generic import ListView

urlpatterns = [

    # Issues
    path('', views.index, {'price': False}, name='index'),
    path('prix-faces', views.index, {'price': True}, name='index'),
    path('numeros/', views.archives, name='archives'),
    path('numero/<int:number>', views.issue, name='issue'),

    # Shop
    path('shop/', views.shop, name='shop'),
    path('shop/create-checkout-session/<pk>/', views.CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    # path('checkout', views.checkout, name='checkout'),
    # path('charge/', faces_views.charge, name='charge'),
    # path('votre-abonnement/<str:type>/', faces_views.charge_custom, name='charge_custom'),
    path('webhooks/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('votre-abonnement/', views.subscription, name='subscription'),
    path('facture/<str:date>/', views.invoice, name="invoice"),
    # path('factures/', views.Invoices.as_view(), name="invoices"),
    path('factures/', views.invoices, name="invoices"),

    # Staff URLs
    path('subscribers/', views.subscribers, name='subscribers'),
    path('subscribers/<int:number>/', views.issue_subscribers, name='subscribers_issue'),
    path('subscribers/<int:number>/export/<str:region>/', views.issue_subscribers_export, name='subscribers_issue_export'),

    # Captcha
    re_path(r'^captcha/', include('captcha.urls')),
]



# from shop.views import (
#     CreateCheckoutSessionView,
#     Landing,
#     Cancel,
#     Success,
#     stripe_webhook,
# )

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('create-checkout-session/<str:product>/', CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
#     path('', Landing.as_view(), name='landing-page'),
#     path('cancel/', Cancel.as_view(), name='cancel-page'),
#     path('success/', Success.as_view(), name='success-page'),
#     path('webhooks/stripe/', stripe_webhook, name='stripe_webhook'),
# ]
