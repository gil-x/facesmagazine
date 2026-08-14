"""
Tests de fumée des parcours publics et boutique.

Ils ne cherchent pas l'exhaustivité : ils vérifient que chaque page se rend,
que les accès réservés sont bien fermés et que les exports produisent les
colonnes attendues. C'est le filet de sécurité des montées de version.
"""
from datetime import date
from unittest.mock import patch

from captcha.models import CaptchaStore
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings

from .models import Customer, Issue, Order, Page, Setting, Subscription
from .templatetags import magazine_extras


class ReferenceDataMixin:
    """Jeu de données minimal reproduisant la structure du site en production."""

    @classmethod
    def setUpTestData(cls):
        # Presque toutes les vues lisent Setting.objects.first() sans garde :
        # cette ligne doit exister pour que le site réponde.
        cls.setting = Setting.objects.create(users=True, shop=True, next_issue=87)

        cls.page = Page.objects.create(label="la revue", position=1, body="<p>Texte</p>")
        Page.objects.create(label="prix Faces", position=4, body="<p>Prix</p>")

        cls.issue = Issue.objects.create(
            number=86, theme="Habiter", date="hiver 2025", stock=6, color="808C74",
        )
        cls.sold_out_issue = Issue.objects.create(
            number=85, theme="Seuils", date="automne 2025", stock=0,
        )

        cls.subscription = Subscription.objects.create(
            region="SUISSE", name="Abonnement 4 numéros",
            number=4, price=40.0, currency="CHF",
        )

        cls.user = User.objects.create_user(
            username="lectrice", email="lectrice@example.org", password="motdepasse-solide-42",
        )
        cls.customer = Customer.objects.create(
            user=cls.user, region="SUISSE", delivery_region="SUISSE",
            name="Dupont", firstname="Camille",
            address="12 rue des Alpes", postal_code="1200", city="Genève",
            land="Suisse", delivery_name="Dupont", delivery_firstname="Camille",
            delivery_address="12 rue des Alpes", delivery_postal_code="1200",
            delivery_city="Genève", delivery_land="Suisse", delivery_postal_square="CP 42",
        )

        cls.staff = User.objects.create_user(
            username="redaction", email="redaction@example.org",
            password="motdepasse-solide-42", is_staff=True,
        )


class PublicPagesTests(ReferenceDataMixin, TestCase):
    def test_accueil(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # Le dernier numéro pilote l'affichage et la couleur de fond.
        self.assertEqual(response.context["last_issue"], self.issue)

    def test_accueil_prix_faces_ouvre_le_menu(self):
        """L'URL /prix-faces affiche la même page, menu latéral déplié."""
        response = self.client.get("/prix-faces")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["price"])
        self.assertNotIn("price", self.client.get("/").context)

    def test_archives_separe_disponibles_et_epuises(self):
        response = self.client.get("/numeros/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.issue, response.context["issues_availables"])
        self.assertIn(self.sold_out_issue, response.context["issues_empty"])

    def test_detail_numero(self):
        response = self.client.get(f"/numero/{self.issue.number}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Habiter")

    def test_numero_sans_image_se_rend_quand_meme(self):
        """Les gabarits appellent .url sans garde : vérifions que ça ne casse pas."""
        self.assertFalse(self.issue.thumbnail)
        self.assertEqual(self.client.get("/numeros/").status_code, 200)

    def test_mentions_legales(self):
        self.assertEqual(self.client.get("/legal/").status_code, 200)


# django-simple-captcha fige ses réglages à l'import de captcha.conf.settings :
# override_settings n'a donc aucun effet, il faut patcher le module du paquet.
@patch("captcha.conf.settings.CAPTCHA_TEST_MODE", True)
@override_settings(CONTACT_RECIPIENTS=["redaction@example.org", "info@example.org"])
class ContactFormTests(ReferenceDataMixin, TestCase):
    """Le formulaire est protégé par un captcha et un champ leurre (honeypot)."""

    def _valid_payload(self, **overrides):
        payload = {
            "subject": "Question sur un numéro",
            "message": "Bonjour, le numéro 80 est-il encore disponible ?",
            "email": "curieux@example.org",
            "captcha_0": CaptchaStore.generate_key(),
            "captcha_1": "PASSED",
            "name": "",  # champ leurre : doit rester vide
        }
        payload.update(overrides)
        return payload

    def test_affichage(self):
        self.assertEqual(self.client.get("/contact/").status_code, 200)

    def test_envoi_valide(self):
        response = self.client.post("/contact/", self._valid_payload())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "magazine/thanks.html")
        # Un message distinct par destinataire, pour ne pas divulguer les adresses.
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual([message.to for message in mail.outbox],
                         [["redaction@example.org"], ["info@example.org"]])
        self.assertIn("Question sur un numéro", mail.outbox[0].subject)

    def test_copie_a_l_expediteur(self):
        self.client.post("/contact/", self._valid_payload(copy="on"))
        destinataires = {adresse for message in mail.outbox for adresse in message.to}
        self.assertIn("curieux@example.org", destinataires)
        self.assertEqual(len(mail.outbox), 3)

    def test_champ_leurre_rempli_est_rejete(self):
        """Un robot qui remplit le champ caché est bloqué avant traitement."""
        response = self.client.post("/contact/", self._valid_payload(name="Robot"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_captcha_invalide_reaffiche_le_formulaire(self):
        response = self.client.post("/contact/", self._valid_payload(captcha_1="RATE"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "magazine/contact.html")
        self.assertEqual(response.context["error"], "True")
        self.assertEqual(len(mail.outbox), 0)


class ShopAccessTests(ReferenceDataMixin, TestCase):
    def test_boutique_reservee_aux_connectes(self):
        response = self.client.get("/shop/")
        self.assertRedirects(response, "/accounts/login/?next=/shop/")

    def test_profil_complet_expose_la_cle_stripe(self):
        self.client.force_login(self.user)
        response = self.client.get("/shop/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_is_complete"])
        self.assertIn("key", response.context)
        # Les abonnements proposés suivent la région de livraison du client.
        self.assertIn(self.subscription, response.context["subscriptions"])

    def test_profil_incomplet_masque_le_paiement(self):
        self.customer.address = ""
        self.customer.save()
        self.client.force_login(self.user)
        response = self.client.get("/shop/")
        self.assertFalse(response.context["profile_is_complete"])
        self.assertNotIn("key", response.context)

    def test_abonne_est_renvoye_vers_son_profil(self):
        self.customer.subscriber = True
        self.customer.save()
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get("/shop/"), "/accounts/profile/")


class InvoiceTests(ReferenceDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.order = Order.objects.create(
            customer=cls.customer, item="SUBSC", subscription=cls.subscription,
            date=date(2026, 3, 11), amount=40.0, currency="CHF",
            order_info="N° 87-88-89-90",
        )

    def test_facture_reservee_aux_connectes(self):
        response = self.client.get(f"/facture/{self.order.date}/")
        self.assertRedirects(response, f"/accounts/login/?next=/facture/{self.order.date}/")

    def test_client_voit_sa_facture(self):
        self.client.force_login(self.user)
        response = self.client.get(f"/facture/{self.order.date}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"], self.order)

    def test_liste_des_factures_reservee_au_staff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/factures/").status_code, 302)

        self.client.force_login(self.staff)
        response = self.client.get("/factures/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.order, response.context["invoices"])


class StaffExportTests(ReferenceDataMixin, TestCase):
    """Les listes d'envoi alimentent le routage postal de chaque numéro."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.customer.subscriber = True
        cls.customer.first_issue = 86
        cls.customer.save()

    def test_liste_des_abonnes_reservee_au_staff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/subscribers/").status_code, 302)

    def test_abonnes_d_un_numero(self):
        self.client.force_login(self.staff)
        response = self.client.get("/subscribers/86/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.customer, response.context["customers"])

    def test_export_csv_france(self):
        self.client.force_login(self.staff)
        response = self.client.get("/subscribers/86/export/france/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("liste-envoi-faces86-france.csv", response["Content-Disposition"])

    def test_export_csv_suisse_ajoute_la_case_postale(self):
        """La Suisse a une colonne supplémentaire, insérée en 5e position."""
        self.client.force_login(self.staff)
        response = self.client.get("/subscribers/86/export/suisse/")
        lignes = response.content.decode("utf-8").splitlines()
        self.assertIn("CASE POSTALE", lignes[0])
        self.assertEqual(lignes[0].split(",")[4], "CASE POSTALE")
        self.assertIn("CP 42", lignes[1])


class StripeWebhookTests(TestCase):
    def test_signature_invalide_est_rejetee(self):
        """Sans signature Stripe valide, aucune commande ne doit être créée."""
        response = self.client.post(
            "/webhooks/stripe/",
            data='{"type": "checkout.session.completed"}',
            content_type="application/json",
            headers={"stripe-signature": "t=1,v1=signature_bidon"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


class TemplateFilterTests(TestCase):
    """Filtres utilisés sur les factures : montants en centimes, HT et TVA."""

    def test_x100_convertit_en_centimes(self):
        self.assertEqual(magazine_extras.x100(40.0), "4000")

    def test_ht_et_tva_se_recomposent(self):
        prix = 40.0
        ht = float(magazine_extras.ht(prix))
        tva = float(magazine_extras.vat(prix))
        self.assertAlmostEqual(ht + tva, prix, places=6)
