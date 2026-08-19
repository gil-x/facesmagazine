"""
Tests de la commande de purge des comptes robots.

La commande supprime définitivement des données : chaque critère de
conservation est vérifié séparément, et le mode simulation aussi.
"""
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .models import Customer, Order, Setting, Subscription


class PurgeSpamAccountsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Setting.objects.create(users=True, shop=True, next_issue=87)
        cls.abonnement = Subscription.objects.create(
            region="SUISSE", name="4 numéros", number=4, price=40.0, currency="CHF",
        )

        # Comptes à conserver, un par critère.
        cls.equipe = cls._compte("redaction", is_staff=True)
        cls.admin = cls._compte("direction", is_superuser=True)
        cls.abonne = cls._compte("abonne")
        Customer.objects.create(user=cls.abonne, subscriber=True)

        cls.acheteur = cls._compte("acheteur")
        profil_acheteur = Customer.objects.create(user=cls.acheteur)
        Order.objects.create(
            customer=profil_acheteur, item='SUBSC', subscription=cls.abonnement,
            date=date(2026, 3, 11), amount=40.0, currency="CHF",
        )

        cls.resident = cls._compte("resident")
        Customer.objects.create(user=cls.resident, address="12 rue des Alpes", city="Genève")

        # Comptes à supprimer.
        cls.robot_actif = cls._compte("aoTqqqibNmLEwKXmg")
        Customer.objects.create(user=cls.robot_actif)  # profil vide créé à l'activation
        cls.robot_inactif = cls._compte("cwOjBBYdBIokvIZ", is_active=False)

    @classmethod
    def _compte(cls, username, **flags):
        return User.objects.create_user(
            username=username, email=f"{username}@example.org",
            password="motdepasse-solide-42", **flags,
        )

    def purger(self, *arguments):
        sortie = StringIO()
        call_command('purge_spam_accounts', *arguments, stdout=sortie)
        return sortie.getvalue()

    def test_simulation_ne_supprime_rien(self):
        avant = User.objects.count()
        rapport = self.purger()
        self.assertEqual(User.objects.count(), avant)
        self.assertIn("Simulation", rapport)

    def test_simulation_annonce_le_bon_nombre(self):
        self.assertIn("Comptes supprimés : 2 sur 7", self.purger())

    def test_conserve_l_equipe_meme_sans_adresse(self):
        """Le compte d'administration de l'association n'a pas de profil rempli."""
        self.purger('--apply')
        self.assertTrue(User.objects.filter(pk=self.equipe.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_conserve_abonnes_acheteurs_et_adresses(self):
        self.purger('--apply')
        for compte in (self.abonne, self.acheteur, self.resident):
            self.assertTrue(
                User.objects.filter(pk=compte.pk).exists(),
                f"{compte.username} aurait dû être conservé",
            )

    def test_supprime_les_comptes_sans_activite(self):
        self.purger('--apply')
        self.assertFalse(User.objects.filter(pk=self.robot_actif.pk).exists())
        self.assertFalse(User.objects.filter(pk=self.robot_inactif.pk).exists())

    def test_aucune_commande_perdue(self):
        """La cascade utilisateur → profil → commande ne doit rien emporter."""
        self.purger('--apply')
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(User.objects.count(), 5)

    def test_le_profil_vide_du_robot_part_avec_lui(self):
        self.purger('--apply')
        self.assertFalse(Customer.objects.filter(user_id=self.robot_actif.pk).exists())

    def test_relance_sans_effet(self):
        """Une seconde exécution ne doit plus rien trouver à supprimer."""
        self.purger('--apply')
        restants = User.objects.count()
        self.assertIn("Comptes supprimés : 0", self.purger('--apply'))
        self.assertEqual(User.objects.count(), restants)
