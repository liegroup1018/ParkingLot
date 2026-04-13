import pyotp
from django.shortcuts import render, redirect
from django.views import View
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.accounts.models import UserRole


class AdminLoginView(View):
    """
    Session-based login for administrators.
    Requires username, password, and TOTP code.
    """
    def get(self, request):
        if request.user.is_authenticated and request.user.role == UserRole.ADMIN:
            return redirect("admin_dashboard")
        return render(request, "admin_ui/login.html")

    def post(self, request):
        username = request.POST.get("username")
        password = request.POST.get("password")
        totp_code = request.POST.get("totp_code")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, "admin_ui/login.html")

        if user.role != UserRole.ADMIN:
            messages.error(request, "Access denied. Administrator privileges required.")
            return render(request, "admin_ui/login.html")

        if not user.has_2fa_configured:
            messages.error(request, "2FA is not configured for this admin account yet. Please setup via API.")
            return render(request, "admin_ui/login.html")

        totp = pyotp.TOTP(user.two_factor_secret)
        if not totp.verify(totp_code, valid_window=1):
            messages.error(request, "Invalid TOTP code. Please try again.")
            return render(request, "admin_ui/login.html")

        login(request, user)
        next_url = request.GET.get("next")
        if next_url:
            return redirect(next_url)
        return redirect("admin_dashboard")


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "admin_ui/dashboard.html"

    def test_func(self):
        return self.request.user.role == UserRole.ADMIN
