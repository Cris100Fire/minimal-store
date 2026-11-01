from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import FormView

from .forms import RegisterForm


class UserLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegisterForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class UserLogoutView(LogoutView):
    next_page = reverse_lazy("accounts:login")
