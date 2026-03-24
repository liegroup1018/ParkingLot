from django.urls import path
from apps.payments.views import TicketScanView, PaymentProcessView

urlpatterns = [
    path("tickets/scan", TicketScanView.as_view(), name="ticket-scan"),
    path("payments", PaymentProcessView.as_view(), name="process-payment"),
]
