from django.contrib import admin
from django.db import models

from .models import Setting, Page, Issue, Subscription, Customer, Order
from .widgets import TrixWidget


class ContenuEditorialAdmin(admin.ModelAdmin):
    """Administration des modèles dont les champs longs contiennent du HTML.

    Tous les TextField de Page et Issue sont du contenu éditorial : édito,
    sommaire, extrait, textes des pages. Ils sont donc édités avec Trix.
    """

    formfield_overrides = {
        models.TextField: {'widget': TrixWidget},
    }


@admin.register(Page)
class PageAdmin(ContenuEditorialAdmin):
    pass


@admin.register(Issue)
class IssueAdmin(ContenuEditorialAdmin):
    pass


admin.site.register(Setting)
admin.site.register(Subscription)
admin.site.register(Customer)
admin.site.register(Order)
