from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from magazine import views as magazine_views

urlpatterns = [

    path('', include('magazine.urls')),

    # Account
    path('accounts/', include('users.urls')),

    # Contact
    path('contact/', magazine_views.contact_captcha, name='contact_captcha'),

    # Legal
    path('legal/', magazine_views.Legal.as_view(), name='legal'),

    # admin
    path('admin/', include('admin_honeypot.urls', namespace='admin_honeypot')),
    path('backdoor/', admin.site.urls),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
