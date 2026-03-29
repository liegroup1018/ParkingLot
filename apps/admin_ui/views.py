from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "admin_ui/dashboard.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == "Admin"
