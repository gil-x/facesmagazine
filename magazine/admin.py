from django.contrib import admin
from .models import Setting, Page, Issue, Subscription, Customer, Order

admin.site.register(Setting)
admin.site.register(Page)
admin.site.register(Issue)
admin.site.register(Subscription)
admin.site.register(Customer)
admin.site.register(Order)