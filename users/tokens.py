from django.contrib.auth.tokens import PasswordResetTokenGenerator


class TokenGenerator(PasswordResetTokenGenerator):
    """Jeton d'activation de compte, invalidé dès que le compte est activé."""

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{timestamp}{user.is_active}"


account_activation_token = TokenGenerator()
