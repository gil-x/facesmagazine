"""
Tests de fumée du parcours de compte : inscription, activation par e-mail,
connexion, déconnexion et édition du profil client.
"""
import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase

from magazine.models import Customer, Issue, Page, Setting


class AccountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Les redirections aboutissent sur l'accueil, qui suppose qu'un
        # Setting et au moins un numéro existent en base.
        Setting.objects.create(users=True, shop=True, next_issue=87)
        Page.objects.create(label="la revue", position=1, body="<p>Texte</p>")
        Issue.objects.create(number=86, theme="Habiter", date="hiver 2025", stock=6)

    def register(self, username="nouvelle", email="nouvelle@example.org"):
        return self.client.post("/accounts/inscription/", {
            "username": username,
            "email": email,
            "password1": "motdepasse-solide-42",
            "password2": "motdepasse-solide-42",
        })


class RegistrationTests(AccountTestCase):
    def test_affichage_du_formulaire(self):
        self.assertEqual(self.client.get("/accounts/inscription/").status_code, 200)

    def test_inscription_cree_un_compte_inactif(self):
        """Le compte reste inactif tant que l'adresse n'est pas confirmée."""
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/confirmation.html")

        utilisateur = User.objects.get(username="nouvelle")
        self.assertFalse(utilisateur.is_active)
        # Le profil client n'est créé qu'à l'activation.
        self.assertFalse(Customer.objects.filter(user=utilisateur).exists())

    def test_un_mail_d_activation_est_envoye(self):
        self.register()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nouvelle@example.org"])
        self.assertIn("Activez votre compte", mail.outbox[0].subject)


class ActivationTests(AccountTestCase):
    def activation_url(self):
        """Extrait le lien d'activation du message envoyé à l'inscription."""
        self.register()
        lien = re.search(r"/accounts/activate/\S+", mail.outbox[0].body)
        self.assertIsNotNone(lien, "aucun lien d'activation dans le message")
        return lien.group(0).rstrip("/") + "/"

    def test_le_lien_active_le_compte_et_cree_le_profil(self):
        response = self.client.get(self.activation_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/activation_success.html")

        utilisateur = User.objects.get(username="nouvelle")
        self.assertTrue(utilisateur.is_active)
        self.assertTrue(Customer.objects.filter(user=utilisateur).exists())

    def test_le_lien_active_ouvre_la_session(self):
        self.client.get(self.activation_url())
        self.assertEqual(self.client.get("/accounts/profile/").status_code, 200)

    def test_jeton_invalide_refuse_l_activation(self):
        url = self.activation_url()
        falsifie = url[:-6] + "abcde/"
        response = self.client.get(falsifie)
        self.assertTemplateUsed(response, "registration/activation_fail.html")
        self.assertFalse(User.objects.get(username="nouvelle").is_active)

    def test_le_jeton_ne_sert_qu_une_fois(self):
        """Le jeton dépend de is_active : il expire dès la première activation."""
        url = self.activation_url()
        self.client.get(url)
        self.client.logout()

        response = self.client.get(url)
        self.assertTemplateUsed(response, "registration/activation_fail.html")


class LoginTests(AccountTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(
            username="lectrice", email="lectrice@example.org",
            password="motdepasse-solide-42",
        )

    def test_connexion_par_identifiant(self):
        response = self.client.post("/accounts/login/", {
            "username": "lectrice", "password": "motdepasse-solide-42",
        })
        self.assertRedirects(response, "/")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_connexion_par_adresse_email(self):
        """Un backend maison autorise l'e-mail à la place de l'identifiant."""
        response = self.client.post("/accounts/login/", {
            "username": "lectrice@example.org", "password": "motdepasse-solide-42",
        })
        self.assertRedirects(response, "/")

    def test_connexion_insensible_a_la_casse(self):
        response = self.client.post("/accounts/login/", {
            "username": "LECTRICE@Example.ORG", "password": "motdepasse-solide-42",
        })
        self.assertRedirects(response, "/")

    def test_mauvais_mot_de_passe(self):
        response = self.client.post("/accounts/login/", {
            "username": "lectrice", "password": "mauvais",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_compte_inactif_refuse(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post("/accounts/login/", {
            "username": "lectrice", "password": "motdepasse-solide-42",
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deconnexion_en_post(self):
        self.client.force_login(self.user)
        response = self.client.post("/accounts/logout/", {"next": "/"})
        self.assertRedirects(response, "/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_deconnexion_en_get_refusee(self):
        """Django 5 n'accepte plus la déconnexion par simple lien."""
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)


class ProfileTests(AccountTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.user = User.objects.create_user(
            username="lectrice", email="lectrice@example.org",
            password="motdepasse-solide-42",
        )
        cls.customer = Customer.objects.create(user=cls.user)

    def test_profil_reserve_aux_connectes(self):
        response = self.client.get("/accounts/profile/")
        self.assertRedirects(response, "/accounts/login/?next=/accounts/profile/")

    def test_profil_incomplet_signale(self):
        self.client.force_login(self.user)
        response = self.client.get("/accounts/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["profile_is_complete"])

    def test_edition_du_profil(self):
        self.client.force_login(self.user)
        response = self.client.post("/accounts/profile/edit", {
            "region": "SUISSE", "name": "Dupont", "firstname": "Camille",
            "address": "12 rue des Alpes", "postal_code": "1200",
            "city": "Genève", "land": "Suisse",
            "delivery_region": "SUISSE", "delivery_name": "Dupont",
            "delivery_firstname": "Camille", "delivery_address": "12 rue des Alpes",
            "delivery_postal_code": "1200", "delivery_city": "Genève",
            "delivery_land": "Suisse",
        })
        self.assertRedirects(response, "/accounts/profile/")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.city, "Genève")
        self.assertTrue(
            self.client.get("/accounts/profile/").context["profile_is_complete"]
        )
