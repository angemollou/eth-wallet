import re
from django.contrib.auth.password_validation import MinimumLengthValidator
from django.conf import settings


class Validator:

    @classmethod
    def password(cls, password):
        if password is None:
            return False

        min_length = next(
            filter(
                lambda module: module["NAME"]
                == "django.contrib.auth.password_validation.MinimumLengthValidator",
                settings.AUTH_PASSWORD_VALIDATORS,
            )
        )["OPTIONS"]["min_length"]
        MinimumLengthValidator(min_length).validate(password=password)

        return True

    @classmethod
    def container_name(cls, name: str):
        return re.search(r"^[a-z0-9][a-z0-9_-]*$", name) is not None
