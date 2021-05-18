from django import template

register = template.Library()

@register.filter
def x100(price):   
    return str(int(price * 100))


@register.filter
def ht(price):   
    return str(price - price * 0.025)

@register.filter
def vat(price):   
    return str(price * 0.025)