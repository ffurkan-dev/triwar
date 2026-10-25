from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import User


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="Şifre", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Şifre (tekrar)", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["email", "username"]
        labels = {"email": "E-posta", "username": "Kullanıcı adı"}
        error_messages = {
            "email": {"invalid": "Geçerli bir e-posta adresi gir."},
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu e-posta ile zaten bir hesap var.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Bu kullanıcı adı alınmış.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Şifreler eşleşmiyor.")
        elif p1:
            candidate = User(email=cleaned.get("email", ""), username=cleaned.get("username", ""))
            try:
                password_validation.validate_password(p1, candidate)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="E-posta", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}))
    password = forms.CharField(label="Şifre", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    error_messages = {
        "invalid_login": "E-posta veya şifre hatalı.",
        "inactive": "Bu hesap devre dışı.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
