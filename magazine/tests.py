"""
Tests de fumée des parcours publics et boutique.

Ils ne cherchent pas l'exhaustivité : ils vérifient que chaque page se rend,
que les accès réservés sont bien fermés et que les exports produisent les
colonnes attendues. C'est le filet de sécurité des montées de version.
"""
import time
from datetime import date
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.core import signing
from django.test import TestCase, override_settings

from facesmagazine.antibot import SEL, reponse_attendue

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


@override_settings(CONTACT_RECIPIENTS=["redaction@example.org", "info@example.org"])
class ContactFormTests(ReferenceDataMixin, TestCase):
    """Formulaire ouvert aux visiteurs non inscrits, donc le plus exposé.

    Le captcha a été retiré : le lectorat de la revue est âgé et il écartait
    autant de lecteurs que de robots. Il est remplacé par les contrôles
    invisibles de HumanCheckMixin, vérifiés ici.
    """

    def _valid_payload(self, **overrides):
        jeton = signing.dumps(time.time() - 10, salt=SEL)
        payload = {
            "subject": "Question sur un numéro",
            "message": "Bonjour, le numéro 80 est-il encore disponible ?",
            "email": "curieux@example.org",
            "ouverture": jeton,
            "presence": reponse_attendue(jeton),
            "name": "",  # champ leurre : doit rester vide
        }
        payload.update(overrides)
        return payload

    def test_affichage(self):
        self.assertEqual(self.client.get("/contact/").status_code, 200)

    def test_plus_aucun_captcha(self):
        contenu = self.client.get("/contact/").content.decode("utf-8")
        self.assertNotIn("captcha", contenu.lower())
        self.assertIn('name="ouverture"', contenu)
        self.assertIn('name="presence"', contenu)

    def test_sans_javascript_le_message_est_refuse(self):
        response = self.client.post("/contact/", self._valid_payload(presence=""))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "magazine/contact.html")
        self.assertEqual(len(mail.outbox), 0)

    def test_envoi_trop_rapide_refuse(self):
        jeton = signing.dumps(time.time(), salt=SEL)
        response = self.client.post("/contact/", self._valid_payload(
            ouverture=jeton, presence=reponse_attendue(jeton),
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

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

    def test_formulaire_incomplet_reaffiche_la_page(self):
        response = self.client.post("/contact/", self._valid_payload(email="pas-une-adresse"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "magazine/contact.html")
        self.assertEqual(response.context["error"], "True")
        self.assertEqual(len(mail.outbox), 0)


class ShopAccessTests(ReferenceDataMixin, TestCase):
    def test_boutique_reservee_aux_connectes(self):
        response = self.client.get("/shop/")
        self.assertRedirects(response, "/accounts/login/?next=/shop/")

    def test_profil_complet_ouvre_le_paiement(self):
        self.client.force_login(self.user)
        response = self.client.get("/shop/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["profile_is_complete"])
        # Les abonnements proposés suivent la région de livraison du client.
        self.assertIn(self.subscription, response.context["subscriptions"])

    def test_profil_incomplet_masque_le_paiement(self):
        self.customer.address = ""
        self.customer.save()
        self.client.force_login(self.user)
        response = self.client.get("/shop/")
        self.assertFalse(response.context["profile_is_complete"])

    def test_aucun_script_tiers_sur_la_page_de_paiement(self):
        """polyfill.io a été compromis en 2024 ; plus aucun script externe ici."""
        self.client.force_login(self.user)
        contenu = self.client.get("/shop/").content.decode("utf-8")
        self.assertNotIn("polyfill.io", contenu)
        self.assertNotIn("js.stripe.com", contenu)

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


class CreateCheckoutSessionTests(ReferenceDataMixin, TestCase):
    """La session de paiement est créée côté serveur, jamais dans le navigateur."""

    def url(self, subscription=None):
        pk = (subscription or self.subscription).pk
        return f"/shop/create-checkout-session/{pk}/"

    def test_anonyme_refuse(self):
        """Sans ce garde-fou, une session serait ouverte sans utilisateur."""
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_refuse(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_abonnement_inconnu(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post("/shop/create-checkout-session/9999/").status_code, 404)

    def test_compte_sans_profil_client(self):
        self.customer.delete()
        self.client.force_login(self.user)
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 400)

    @patch("magazine.views.stripe.checkout.Session.create")
    def test_session_creee_et_url_renvoyee(self, session_create):
        session_create.return_value = Mock(url="https://checkout.stripe.com/c/pay/cs_test_1")
        self.client.force_login(self.user)

        response = self.client.post(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"url": "https://checkout.stripe.com/c/pay/cs_test_1"})

        arguments = session_create.call_args.kwargs
        prix = arguments["line_items"][0]["price_data"]
        # Stripe attend des centimes entiers et un code devise en minuscules.
        self.assertEqual(prix["unit_amount"], 4000)
        self.assertEqual(prix["currency"], "chf")
        self.assertEqual(arguments["mode"], "payment")
        self.assertEqual(arguments["customer_email"], self.user.email)
        self.assertEqual(arguments["metadata"], {
            "user_id": self.user.id, "subscription_id": self.subscription.id,
        })

    @patch("magazine.views.stripe.checkout.Session.create")
    def test_montant_arrondi_au_centime(self, session_create):
        """22.10 € en flottant vaut 2209.9999… centimes : il faut arrondir."""
        session_create.return_value = Mock(url="https://checkout.stripe.com/c/pay/cs_test_2")
        self.subscription.price = 22.10
        self.subscription.save()
        self.client.force_login(self.user)

        self.client.post(self.url())

        prix = session_create.call_args.kwargs["line_items"][0]["price_data"]
        self.assertEqual(prix["unit_amount"], 2210)


class StripeWebhookTests(ReferenceDataMixin, TestCase):
    ENDPOINT = "/webhooks/stripe/"

    def evenement(self, session_id="cs_test_1", **metadata_overrides):
        metadata = {
            "user_id": str(self.user.id),
            "subscription_id": str(self.subscription.id),
        }
        metadata.update(metadata_overrides)
        return {
            "type": "checkout.session.completed",
            "data": {"object": {"id": session_id, "metadata": metadata}},
        }

    def appel(self):
        return self.client.post(
            self.ENDPOINT, data="{}", content_type="application/json",
            headers={"stripe-signature": "t=1,v1=peu_importe"},
        )

    def test_sans_entete_de_signature(self):
        """Auparavant l'absence d'en-tête provoquait une erreur 500."""
        response = self.client.post(
            self.ENDPOINT, data="{}", content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_signature_invalide_est_rejetee(self):
        response = self.appel()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_get_refuse(self):
        self.assertEqual(self.client.get(self.ENDPOINT).status_code, 405)

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_paiement_enregistre_l_abonnement(self, construct_event):
        construct_event.return_value = self.evenement()

        self.assertEqual(self.appel().status_code, 200)

        self.customer.refresh_from_db()
        self.assertTrue(self.customer.subscriber)
        self.assertEqual(self.customer.subscription, self.subscription)
        self.assertEqual(self.customer.first_issue, 87)

        commande = Order.objects.get()
        self.assertEqual(commande.customer, self.customer)
        self.assertEqual(commande.amount, 40.0)
        self.assertEqual(commande.currency, "CHF")
        self.assertEqual(commande.stripe_session_id, "cs_test_1")
        # Les quatre numéros couverts par l'abonnement.
        self.assertEqual(commande.order_info, "N° 87-88-89-90")

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_un_seul_mail_de_confirmation(self, construct_event):
        construct_event.return_value = self.evenement()
        self.appel()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_rejeu_ne_duplique_pas_la_commande(self, construct_event):
        """Stripe rejoue ses événements : le traitement doit être idempotent."""
        construct_event.return_value = self.evenement()

        self.appel()
        with self.assertLogs("magazine.views", level="INFO") as journal:
            self.appel()
            self.appel()

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(journal.records), 2)
        self.assertIn("déjà traitée", journal.output[0])

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_deux_paiements_distincts_creent_deux_commandes(self, construct_event):
        construct_event.return_value = self.evenement(session_id="cs_test_1")
        self.appel()
        construct_event.return_value = self.evenement(session_id="cs_test_2")
        self.appel()

        self.assertEqual(Order.objects.count(), 2)

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_metadonnees_inexploitables_sont_ignorees(self, construct_event):
        """Un utilisateur supprimé entre-temps ne doit pas faire échouer l'accusé."""
        construct_event.return_value = self.evenement(user_id="999999")

        with self.assertLogs("magazine.views", level="ERROR") as journal:
            self.assertEqual(self.appel().status_code, 200)

        self.assertEqual(Order.objects.count(), 0)
        self.assertIn("inexploitable", journal.output[0])

    @patch("magazine.views.stripe.Webhook.construct_event")
    def test_autre_type_d_evenement_ignore(self, construct_event):
        construct_event.return_value = {"type": "payment_intent.created", "data": {"object": {}}}

        self.assertEqual(self.appel().status_code, 200)
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
