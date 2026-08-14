"""
Tests de fumée du parcours de compte : inscription, activation par e-mail,
connexion, déconnexion et édition du profil client.
"""
import re
import time
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core import signing
from django.test import TestCase

from facesmagazine.antibot import DELAI_MAXIMUM, SEL, reponse_attendue
from magazine.models import Customer, Issue, Page, Setting

MOT_DE_PASSE = "motdepasse-solide-42"


class AccountTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Les redirections aboutissent sur l'accueil, qui suppose qu'un
        # Setting et au moins un numéro existent en base.
        Setting.objects.create(users=True, shop=True, next_issue=87)
        Page.objects.create(label="la revue", position=1, body="<p>Texte</p>")
        Issue.objects.create(number=86, theme="Habiter", date="hiver 2025", stock=6)

    def payload(self, **overrides):
        """Formulaire d'inscription tel que le poste un navigateur.

        Le jeton est daté de dix secondes plus tôt pour représenter un
        formulaire réellement rempli, sans immobiliser le test.
        """
        jeton = signing.dumps(time.time() - 10, salt=SEL)
        donnees = {
            "username": "nouvelle",
            "email": "nouvelle@example.org",
            "password1": MOT_DE_PASSE,
            "password2": MOT_DE_PASSE,
            "ouverture": jeton,
            "presence": reponse_attendue(jeton),
            "name": "",  # champ leurre
        }
        donnees.update(overrides)
        return donnees

    def register(self, **overrides):
        return self.client.post("/accounts/inscription/", self.payload(**overrides))


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


class AntiBotTests(AccountTestCase):
    """Contrôles invisibles remplaçant le captcha.

    Le lectorat étant âgé et peu à l'aise avec l'informatique, aucun de ces
    contrôles ne doit demander quoi que ce soit à l'utilisateur.
    """

    def assertRefuse(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/registration.html")
        self.assertFalse(User.objects.filter(username="nouvelle").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_sans_javascript_l_inscription_est_refusee(self):
        """Un client HTTP qui poste le formulaire ne remplit pas ce champ."""
        self.assertRefuse(self.register(presence=""))

    def test_champ_de_presence_incorrect(self):
        self.assertRefuse(self.register(presence="n'importe quoi"))

    def test_formulaire_soumis_trop_vite(self):
        """Un robot poste dans la foulée du chargement ; un humain non."""
        jeton = signing.dumps(time.time(), salt=SEL)
        self.assertRefuse(
            self.register(ouverture=jeton, presence=reponse_attendue(jeton))
        )

    def test_jeton_absent(self):
        self.assertRefuse(self.register(ouverture="", presence=""))

    def test_jeton_falsifie(self):
        self.assertRefuse(self.register(ouverture="jeton-inventé", presence="étnevni-notej"))

    def test_jeton_perime(self):
        """Récolter un formulaire une fois ne permet pas de le rejouer des jours.

        Le jeton est forgé en remontant l'horloge, pour que l'horodatage de
        la signature soit lui aussi ancien : c'est lui que contrôle max_age.
        """
        il_y_a_longtemps = time.time() - 5 * DELAI_MAXIMUM
        with patch("django.core.signing.time.time", return_value=il_y_a_longtemps):
            vieux = signing.dumps(il_y_a_longtemps, salt=SEL)

        self.assertRefuse(
            self.register(ouverture=vieux, presence=reponse_attendue(vieux))
        )

    def test_champ_leurre_rempli(self):
        response = self.register(name="Robot")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="nouvelle").exists())

    def test_la_page_fournit_de_quoi_passer_les_controles(self):
        contenu = self.client.get("/accounts/inscription/").content.decode("utf-8")
        self.assertIn('name="ouverture"', contenu)
        self.assertIn('name="presence"', contenu)
        self.assertIn('name="name"', contenu)  # champ leurre
        self.assertNotIn("captcha", contenu.lower())

    def test_parcours_reel_depuis_la_page(self):
        """De bout en bout : on lit le formulaire rendu et on le renvoie."""
        contenu = self.client.get("/accounts/inscription/").content.decode("utf-8")
        jeton = re.search(r'name="ouverture"[^>]*value="([^"]+)"', contenu).group(1)

        with patch("facesmagazine.antibot.DELAI_MINIMUM", 0):
            response = self.client.post("/accounts/inscription/", {
                "username": "nouvelle",
                "email": "nouvelle@example.org",
                "password1": MOT_DE_PASSE,
                "password2": MOT_DE_PASSE,
                "ouverture": jeton,
                "presence": jeton[::-1],
                "name": "",
            })

        self.assertTemplateUsed(response, "registration/confirmation.html")
        self.assertTrue(User.objects.filter(username="nouvelle").exists())


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
            password=MOT_DE_PASSE,
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

    def test_adresse_partagee_par_deux_comptes(self):
        """Django n'impose pas l'unicité des e-mails ; douze lecteurs en partagent un.

        L'ancien backend faisait un get() et renvoyait une erreur 500 à ces
        personnes dès qu'elles tentaient de se connecter par adresse.
        """
        jumeau = User.objects.create_user(
            username="lectrice_bis", email="lectrice@example.org",
            password="un-autre-mot-de-passe-64",
        )

        response = self.client.post("/accounts/login/", {
            "username": "lectrice@example.org", "password": "un-autre-mot-de-passe-64",
        })

        self.assertRedirects(response, "/")
        self.assertEqual(self.client.session["_auth_user_id"], str(jumeau.pk))

    def test_authenticate_sans_identifiant_ne_casse_pas(self):
        """L'ancien backend faisait « '@' in None » et levait une TypeError."""
        from django.contrib.auth import authenticate
        self.assertIsNone(authenticate(username=None, password="peu importe"))
        self.assertIsNone(authenticate(username="lectrice", password=None))

    def test_compte_inactif_refuse_par_le_backend(self):
        """Contrôle au niveau du backend, indépendamment du formulaire."""
        from django.contrib.auth import authenticate
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(
            authenticate(username="lectrice@example.org", password=MOT_DE_PASSE)
        )

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
            password=MOT_DE_PASSE,
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
