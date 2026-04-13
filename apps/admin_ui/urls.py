from django.urls import path
from .views import AdminDashboardView, AdminLoginView

urlpatterns = [
    path("login/", AdminLoginView.as_view(), name="admin_login"),
    path("", AdminDashboardView.as_view(), name="admin_dashboard"),
]
