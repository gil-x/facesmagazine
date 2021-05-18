from django.conf import settings
from django.contrib.auth.models import User

class EmailOrUsernameModelBackend(object):
    def authenticate(self, request, username=None, password=None):
        if '@' in username:
            field = 'email'
        else:
            field = 'username'
        try:

            case_insensitive_username_field = '{}__iexact'.format(field)
            user = User._default_manager.get(**{case_insensitive_username_field: username})

            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
