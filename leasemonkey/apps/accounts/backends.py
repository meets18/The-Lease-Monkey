from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User

class MultiBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None
        try:
            # Query by username, email, or phone_number
            user = User.objects.get(
                Q(username__iexact=username) |
                Q(email__iexact=username) |
                Q(phone_number=username)
            )
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None
