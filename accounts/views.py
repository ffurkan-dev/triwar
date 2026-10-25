from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import EmailAuthenticationForm, RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("lobby")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("lobby")
    return render(request, "accounts/register.html", {"form": form})


class TriwarLoginView(LoginView):
    authentication_form = EmailAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
