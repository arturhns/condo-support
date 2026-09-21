from django import forms
from django.contrib.auth.forms import AuthenticationForm

from app.models import User


class LoginForm(AuthenticationForm):
    """Login em português; aceita username do seed ou o e-mail correspondente."""

    username = forms.CharField(
        label="Usuário ou e-mail",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "current-password",
            }
        ),
    )

    error_messages = {
        "invalid_login": (
            "Usuário/e-mail ou senha inválidos. "
            "No seed, use o username (ex.: morador1) ou o e-mail (ex.: morador1@condo.local)."
        ),
        "inactive": "Esta conta está inativa.",
    }

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if "@" in username:
            try:
                user = User.objects.get(email__iexact=username)
                return user.get_username()
            except User.DoesNotExist:
                pass
        return username
