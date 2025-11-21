from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Backend de autenticación que permite login con email en lugar de username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Intentar encontrar usuario por email
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            # Si no se encuentra por email, intentar por username
            try:
                user = User.objects.get(username__iexact=username)
            except User.DoesNotExist:
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
