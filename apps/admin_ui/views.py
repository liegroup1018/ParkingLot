from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from apps.accounts.models import UserRole


class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "admin_ui/dashboard.html"

    def test_func(self):
        return self.request.user.role == UserRole.ADMIN
