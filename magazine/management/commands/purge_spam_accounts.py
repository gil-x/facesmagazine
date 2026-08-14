"""
Supprime les comptes créés par des robots.

Le formulaire d'inscription a longtemps été dépourvu de captcha : la table
des utilisateurs s'est remplie de comptes automatiques, y compris activés,
qui n'ont jamais rien fait sur le site.

La commande raisonne par conservation : elle établit la liste des comptes à
garder selon des critères explicites, et supprime tout le reste. Un compte
qui n'entre dans aucun critère de conservation mais qui serait légitime est
donc perdu — d'où le mode simulation par défaut.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from magazine.models import Customer, Order


class Command(BaseCommand):
    help = "Supprime les comptes sans activité réelle (simulation par défaut)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help="Effectue réellement la suppression. Sans cette option, "
                 "la commande se contente d'afficher ce qu'elle ferait.",
        )

    def handle(self, *args, **options):
        # Chaque critère est calculé séparément pour que le rapport indique
        # ce qui protège chaque compte, et non un décompte global opaque.
        equipe = set(
            User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
            .values_list('id', flat=True)
        )
        abonnes = set(
            Customer.objects.filter(subscriber=True).values_list('user_id', flat=True)
        )
        acheteurs = set(
            Order.objects.filter(customer__isnull=False)
            .values_list('customer__user_id', flat=True)
        )
        avec_adresse = set(
            Customer.objects.exclude(address__isnull=True).exclude(address='')
            .values_list('user_id', flat=True)
        )

        a_garder = equipe | abonnes | acheteurs | avec_adresse
        a_supprimer = User.objects.exclude(id__in=a_garder)

        total = User.objects.count()
        nombre_supprimes = a_supprimer.count()

        self.stdout.write("Comptes conservés :")
        self.stdout.write(f"  équipe (staff ou superutilisateur) : {len(equipe)}")
        self.stdout.write(f"  abonnés                            : {len(abonnes)}")
        self.stdout.write(f"  ayant passé commande               : {len(acheteurs)}")
        self.stdout.write(f"  ayant renseigné une adresse        : {len(avec_adresse)}")
        self.stdout.write(f"  total après recoupement            : {len(a_garder)}")
        self.stdout.write("")
        self.stdout.write(f"Comptes supprimés : {nombre_supprimes} sur {total}")

        # Filet de sécurité : la suppression d'un utilisateur cascade sur son
        # profil client puis sur ses commandes. Aucune commande ne doit
        # disparaître — ce serait de l'historique de facturation.
        commandes_menacees = Order.objects.filter(
            customer__user__in=a_supprimer
        ).count()
        if commandes_menacees:
            raise CommandError(
                f"Interruption : {commandes_menacees} commande(s) seraient "
                f"supprimées par cascade. Aucune modification effectuée."
            )

        profils_menaces = Customer.objects.filter(user__in=a_supprimer).count()
        self.stdout.write(f"Profils client supprimés par cascade : {profils_menaces}")
        self.stdout.write("Commandes supprimées par cascade : 0 (vérifié)")

        if not options['apply']:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Simulation : aucune modification. Relancer avec --apply pour appliquer."
            ))
            return

        with transaction.atomic():
            a_supprimer.delete()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{nombre_supprimes} comptes supprimés. "
            f"Il reste {User.objects.count()} utilisateurs et "
            f"{Order.objects.count()} commandes."
        ))
