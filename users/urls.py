from django.urls import path, re_path, include
from . import views


urlpatterns = [
    path('', include('django.contrib.auth.urls')),
    path('login/', views.LoginWithPages.as_view()),
    path('inscription/', views.registration, name='registration'),
    re_path(r'^activate/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
            views.activate, name='activate'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit', views.edit_profile, name='edit_profile'),
]