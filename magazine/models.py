from django.db import models
from ckeditor.fields import RichTextField
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


REGION_CHOICE = (
    ("FRANCE", "France"),
    ("SUISSE", "Suisse"),
    ("EUROPE", "Europe"),
    ("AUTRE", "Autre"),
    )

CURRENCY_CHOICE = (
    ("EUR", "Euro"),
    ("CHF", "Franc suisse"),
    ("USD", "Dollar US"),
)

ITEM = (
    ('ISSUE', 'issue'),
    ('SUBSC', 'subscription'),
)


class Setting(models.Model):
    users = models.BooleanField(default=False)
    shop = models.BooleanField(default=False)
    next_issue = models.IntegerField(unique=True, verbose_name=u"Premier numéro pour abonnement")

    def __str__(self):
        return "Setting"


class Page(models.Model):
    label = models.CharField(max_length=30, verbose_name=u"Label du menu")
    position = models.IntegerField(default="1")
    body = RichTextField(null=True, blank=True, verbose_name=u"Texte simple ou colonne 1/2")
    body_extra = RichTextField(null=True, blank=True, verbose_name=u"Colonne 2/2")
    footer = RichTextField(null=True, blank=True, verbose_name=u"Mentions en bas de page")

    class Meta:
        ordering = ['position', 'label']

    def __str__(self):
        return f"Menu #{self.position} - {self.label}"


class Issue(models.Model):
    theme = models.CharField(max_length=255, null=True, blank=True, verbose_name=u"Thème")
    number = models.IntegerField(unique=True, verbose_name=u"Numéro")
    number_display = models.CharField(unique=True, null=True, blank=True, max_length=20, verbose_name=u"Numéro affiché (optionnel)")
    thumbnail = models.ImageField(null=True, verbose_name=u"Miniature de couverture (230x377 px)", upload_to="issues/")
    image = models.ImageField(null=True, blank=True, verbose_name=u"Image de couverture seule (608x644 px)", upload_to="issues/")
    date = models.CharField(max_length=50, verbose_name=u"Période")
    price_eur = models.FloatField(default=22, verbose_name=u"Prix en euros")
    price_sfranc = models.FloatField(default=25, verbose_name=u"Prix en francs suisses")
    stock = models.IntegerField(default=0, verbose_name=u"Stock")
    color = models.CharField(max_length=6, default= "808C74", verbose_name=u"Couleur (code hexadécimal)")
    editorial = RichTextField(null=True, blank=True, verbose_name=u"Edito")
    content = RichTextField(null=True, blank=True, verbose_name=u"Sommaire")
    extract = RichTextField(null=True, blank=True, verbose_name=u"Extrait")

    class Meta:
        ordering = ['-number']

    def __str__(self):
        return f"Faces Magazine N°{self.number}"


class Subscription(models.Model):
    region = models.CharField(max_length=10,
            choices=REGION_CHOICE, default="FRANCE", verbose_name=u"Région")
    name = models.CharField(max_length=30, null=True, blank=True, verbose_name=u"Nom")
    description = models.CharField(max_length=100, null=True, blank=True, verbose_name=u"Description")
    number = models.IntegerField(default=4, verbose_name=u"Nombre de numéros")
    price = models.FloatField(null=True, blank=True, verbose_name=u"Prix en euros")
    currency = models.CharField(max_length=12,
            choices=CURRENCY_CHOICE, default="EUROS", verbose_name=u"Devise")

    class Meta:
        ordering = ['price']

    def __str__(self):
        return f"{self.name} {self.region} ({self.number} numéros) = {self.price} {self.currency}"


class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subscriber = models.BooleanField(default=False)
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.CASCADE)
    first_issue = models.IntegerField(null=True, blank=True, verbose_name=u"Premier numéro à envoyer")
    subscription_date = models.DateField(null=True, blank=True)

    # Facturation Address fields:
    name = models.CharField(max_length=25, null=True, blank=True, verbose_name=u"Nom")
    firstname = models.CharField(max_length=20, null=True, blank=True, verbose_name=u"Prénom")
    company = models.CharField(max_length=25, null=True, blank=True, verbose_name=u"Société / Raison sociale")
    region = models.CharField(max_length=10, choices=REGION_CHOICE, default="FRANCE", verbose_name=u"Région*")
    address = models.CharField(max_length=100, null=True, verbose_name=u"Adresse*")
    address_extra = models.CharField(max_length=100, null=True, blank=True, verbose_name=u"Complément Adresse")
    postal_code = models.CharField(max_length=10, null=True, verbose_name=u"Code postal*")
    postal_square = models.CharField(max_length=10, null=True, blank=True, verbose_name=u"Case postale")
    city = models.CharField(max_length=50, null=True, verbose_name=u"Ville*")
    land = models.CharField(max_length=50, null=True, verbose_name=u"Pays*")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name=u"Numéro de téléphone")

    # Delivery Address fields:
    delivery_name = models.CharField(max_length=25, null=True, blank=True, verbose_name=u"Nom")
    delivery_firstname = models.CharField(max_length=20, null=True, blank=True, verbose_name=u"Prénom")
    delivery_company = models.CharField(max_length=25, null=True, blank=True, verbose_name=u"Société / Raison sociale")
    delivery_region = models.CharField(max_length=10, choices=REGION_CHOICE, default="FRANCE", verbose_name=u"Région*")
    delivery_address = models.CharField(max_length=255, null=True, verbose_name=u"Adresse*")
    delivery_address_extra = models.CharField(max_length=100, null=True, blank=True, verbose_name=u"Complément Adresse")
    delivery_postal_code = models.CharField(max_length=10, null=True, verbose_name=u"Code postal*")
    delivery_postal_square = models.CharField(max_length=10, null=True, blank=True, verbose_name=u"Case postale")
    delivery_city = models.CharField(max_length=50, null=True, verbose_name=u"Ville*")
    delivery_land = models.CharField(max_length=50, null=True, verbose_name=u"Pays*")
    delivery_phone = models.CharField(max_length=20, null=True, blank=True, verbose_name=u"Numéro de téléphone")

    # Mail approval:
    approval = models.BooleanField(default=True)

    def clean(self):
        if self.name is None and self.company is None:
            raise ValidationError('Veuillez renseigner au moins un nom ou une raison sociale')
        if self.delivery_name is None and self.delivery_company is None:
            raise ValidationError('Veuillez renseigner au moins un nom ou une raison sociale')

    def __str__(self):
        if self.name:
            return f"Utilisateur {self.user.username} ({self.name})"
        else:
            return f"Utilisateur {self.user.username} (pas de nom / raison sociale)"


class Order(models.Model):
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.CASCADE)
    item = models.CharField(choices=ITEM, max_length=5, null=True, blank=True)
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.CASCADE)
    order_info = models.CharField(max_length=100, null=True, blank=True, verbose_name=u"Informations sur la commande")
    date = models.DateField(null=True, blank=True)
    amount = models.FloatField(null=True, blank=True, verbose_name=u"Montant")
    currency = models.CharField(max_length=12, choices=CURRENCY_CHOICE,
            default="EUROS", verbose_name=u"Devise")

    def __str__(self):
        return f"{self.customer.name} - {self.subscription.name} - {self.date} - {self.amount} {self.currency}" 