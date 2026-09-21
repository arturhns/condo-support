from django.contrib.auth.views import LoginView, LogoutView

from app.forms.auth import LoginForm


class ResidentLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class ResidentLogoutView(LogoutView):
    next_page = None  # usa LOGOUT_REDIRECT_URL do settings
